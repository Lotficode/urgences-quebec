"""Feature engineering : transforme l'historique en exemples d'entraînement.

Pour chaque urgence et chaque heure t, on construit des indices (features) qui
n'utilisent QUE le passé (t et avant), et une cible : le taux d'occupation à t + h.
Utiliser une information du futur pour prédire le futur s'appelle une fuite de
données (data leakage) : le modèle paraîtrait excellent en test et serait inutile
en vrai. tests/test_features.py vérifie que ça n'arrive pas.
"""
import numpy as np
import pandas as pd

DECALAGES = (1, 2, 3, 6, 12, 24, 168)   # 168 h = même heure la semaine précédente
COMPTES = ["patients_presents", "patients_attente_pec", "patients_plus_24h", "civieres_fonctionnelles"]


def grille_horaire(historique: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par urgence et par heure, même si un relevé manque (valeur vide)."""
    series = []
    for permis, groupe in historique.groupby("no_permis", sort=False):
        groupe = groupe.set_index("heure_extraction").sort_index()
        groupe = groupe[~groupe.index.duplicated(keep="last")]
        heures = pd.date_range(groupe.index.min(), groupe.index.max(), freq="h")
        groupe = groupe.reindex(heures)
        groupe["no_permis"] = permis
        groupe[["region", "nom_installation"]] = groupe[["region", "nom_installation"]].ffill().bfill()
        series.append(groupe.rename_axis("heure").reset_index())
    if not series:
        return pd.DataFrame(columns=["heure", "no_permis", "taux_occupation"])
    return pd.concat(series, ignore_index=True)


def ajouter_features(grille: pd.DataFrame, horizon: int) -> pd.DataFrame:
    donnees = grille.sort_values(["no_permis", "heure"]).copy()
    par_urgence = donnees.groupby("no_permis", sort=False)["taux_occupation"]

    donnees["taux_actuel"] = donnees["taux_occupation"]
    for k in DECALAGES:
        donnees[f"taux_il_y_a_{k}h"] = par_urgence.shift(k)
    donnees["moyenne_24h"] = par_urgence.transform(lambda s: s.rolling(24, min_periods=6).mean())
    donnees["moyenne_7j"] = par_urgence.transform(lambda s: s.rolling(168, min_periods=24).mean())
    donnees["tendance_3h"] = donnees["taux_actuel"] - donnees["taux_il_y_a_3h"]

    # Le calendrier de l'heure VISÉE : les urgences suivent un cycle jour/nuit et semaine.
    heure_visee = donnees["heure"] + pd.Timedelta(hours=horizon)
    angle_heure = 2 * np.pi * heure_visee.dt.hour / 24
    angle_jour = 2 * np.pi * heure_visee.dt.dayofweek / 7
    donnees["heure_sin"], donnees["heure_cos"] = np.sin(angle_heure), np.cos(angle_heure)
    donnees["jour_sin"], donnees["jour_cos"] = np.sin(angle_jour), np.cos(angle_jour)
    donnees["fin_de_semaine"] = (heure_visee.dt.dayofweek >= 5).astype(int)
    donnees["mois"] = heure_visee.dt.month

    # Baseline saisonnière : le taux observé 24 h avant l'heure visée (connu à l'instant t).
    donnees["baseline_saisonniere"] = par_urgence.shift(24 - horizon) if horizon <= 24 else np.nan

    donnees["cible"] = par_urgence.shift(-horizon)
    donnees["heure_visee"] = heure_visee
    return donnees


COLONNES_FEATURES = (
    ["taux_actuel"]
    + [f"taux_il_y_a_{k}h" for k in DECALAGES]
    + ["moyenne_24h", "moyenne_7j", "tendance_3h"]
    + COMPTES
    + ["heure_sin", "heure_cos", "jour_sin", "jour_cos", "fin_de_semaine", "mois",
       "moyenne_installation"]
)


def construire_jeu(historique: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Jeu complet (avec les lignes sans cible, utiles pour prédire le présent)."""
    return ajouter_features(grille_horaire(historique), horizon)
