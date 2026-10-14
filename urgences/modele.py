"""Entraînement, évaluation et utilisation du modèle de prévision.

Le modèle prédit le taux d'occupation des civières d'une urgence dans h heures.
On le compare toujours à deux baselines (prédictions « bêtes ») :
  - persistance : « dans h heures ce sera comme maintenant »;
  - saisonnière : « ce sera comme hier à la même heure ».
Un modèle qui ne bat pas ces deux-là n'apporte rien.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from urgences import config
from urgences.features import COLONNES_FEATURES, construire_jeu

HEURES_MINIMUM = 24 * 7        # une semaine d'historique avant d'oser entraîner
PART_TEST = 0.2                # les 20 % les plus récents servent au test


class DonneesInsuffisantes(Exception):
    pass


@dataclass
class ModeleUrgences:
    horizon: int
    median: HistGradientBoostingRegressor
    bas: HistGradientBoostingRegressor      # quantile 10 %
    haut: HistGradientBoostingRegressor     # quantile 90 %
    moyennes_installation: dict
    moyenne_globale: float
    metriques: dict

    def matrice(self, jeu: pd.DataFrame) -> pd.DataFrame:
        jeu = jeu.copy()
        jeu["moyenne_installation"] = jeu["no_permis"].map(self.moyennes_installation)
        jeu["moyenne_installation"] = jeu["moyenne_installation"].fillna(self.moyenne_globale)
        return jeu[COLONNES_FEATURES].astype(float)


def _regresseur(**options) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
        random_state=42, **options,
    )


def _exemples(historique: pd.DataFrame, horizon: int) -> pd.DataFrame:
    jeu = construire_jeu(historique, horizon)
    return jeu.dropna(subset=["cible", "taux_actuel"]).sort_values("heure")


def _ajuster(exemples: pd.DataFrame, horizon: int, metriques: dict) -> ModeleUrgences:
    moyennes = exemples.groupby("no_permis")["cible"].mean().to_dict()
    modele = ModeleUrgences(
        horizon=horizon,
        median=_regresseur(),
        bas=_regresseur(loss="quantile", quantile=0.1),
        haut=_regresseur(loss="quantile", quantile=0.9),
        moyennes_installation=moyennes,
        moyenne_globale=float(exemples["cible"].mean()),
        metriques=metriques,
    )
    X, y = modele.matrice(exemples), exemples["cible"]
    for estimateur in (modele.median, modele.bas, modele.haut):
        estimateur.fit(X, y)
    return modele


def entrainer(historique: pd.DataFrame, horizon: int) -> ModeleUrgences:
    exemples = _exemples(historique, horizon)
    duree = exemples["heure"].max() - exemples["heure"].min() if len(exemples) else pd.Timedelta(0)
    if duree < pd.Timedelta(hours=HEURES_MINIMUM):
        raise DonneesInsuffisantes(
            f"Il faut au moins {HEURES_MINIMUM // 24} jours d'historique "
            f"(actuellement {duree}). Laisse la collecte tourner encore."
        )

    # Validation temporelle : on entraîne sur le passé et on teste sur la période
    # suivante, jamais l'inverse. Les exemples dont la cible tombe après la coupure
    # sont retirés de l'entraînement pour qu'aucune information du test n'y entre.
    coupure = exemples["heure"].quantile(1 - PART_TEST)
    entrainement = exemples[exemples["heure_visee"] <= coupure]
    test = exemples[exemples["heure"] > coupure]

    provisoire = _ajuster(entrainement, horizon, {})
    X_test, y_test = provisoire.matrice(test), test["cible"]
    prediction = provisoire.median.predict(X_test)
    bas, haut = provisoire.bas.predict(X_test), provisoire.haut.predict(X_test)

    saisonniere = test["baseline_saisonniere"]
    masque = saisonniere.notna()
    metriques = {
        "horizon_heures": horizon,
        "exemples_entrainement": int(len(entrainement)),
        "exemples_test": int(len(test)),
        "installations": int(exemples["no_permis"].nunique()),
        "periode_test": [str(test["heure"].min()), str(test["heure"].max())],
        # Erreurs absolues moyennes, en points de pourcentage d'occupation.
        "mae_modele": round(100 * mean_absolute_error(y_test, prediction), 2),
        "mae_persistance": round(100 * mean_absolute_error(y_test, test["taux_actuel"]), 2),
        "mae_saisonniere": round(
            100 * mean_absolute_error(y_test[masque], saisonniere[masque]), 2
        ) if masque.any() else None,
        "couverture_intervalle_80": round(float(np.mean((y_test >= bas) & (y_test <= haut))), 3),
        "entraine_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    metriques["gain_vs_persistance_pct"] = round(
        100 * (1 - metriques["mae_modele"] / metriques["mae_persistance"]), 1
    ) if metriques["mae_persistance"] else None

    # Une fois évalué, le modèle final est réentraîné sur TOUT l'historique.
    return _ajuster(exemples, horizon, metriques)


def predire(modele: ModeleUrgences, historique: pd.DataFrame) -> pd.DataFrame:
    """Prévision à partir du dernier relevé connu de chaque urgence."""
    jeu = construire_jeu(historique, modele.horizon).dropna(subset=["taux_actuel"])
    derniers = jeu.sort_values("heure").groupby("no_permis").tail(1)
    if derniers.empty:
        return pd.DataFrame()
    X = modele.matrice(derniers)
    resultat = derniers[["no_permis", "nom_installation", "region", "heure", "taux_actuel"]].copy()
    resultat["heure_visee"] = derniers["heure_visee"]
    resultat["taux_prevu"] = np.clip(modele.median.predict(X), 0, None)
    resultat["taux_bas"] = np.clip(modele.bas.predict(X), 0, None)
    resultat["taux_haut"] = np.clip(modele.haut.predict(X), 0, None)
    numeriques = ["taux_actuel", "taux_prevu", "taux_bas", "taux_haut"]
    resultat[numeriques] = resultat[numeriques].round(4)
    return resultat.reset_index(drop=True)


def chemin(horizon: int):
    return config.DOSSIER_MODELES / f"modele_{horizon}h.joblib"


def sauvegarder(modele: ModeleUrgences) -> None:
    config.DOSSIER_MODELES.mkdir(parents=True, exist_ok=True)
    joblib.dump(modele, chemin(modele.horizon))


def charger(horizon: int) -> ModeleUrgences | None:
    fichier = chemin(horizon)
    return joblib.load(fichier) if fichier.exists() else None
