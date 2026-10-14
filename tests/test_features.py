import pandas as pd

from urgences.features import COLONNES_FEATURES, construire_jeu

HORIZON = 4


def test_la_cible_est_le_taux_dans_h_heures(historique_demo):
    jeu = construire_jeu(historique_demo, HORIZON)
    une = jeu[jeu["no_permis"] == "DEMO001"].reset_index(drop=True)
    assert une.loc[10, "cible"] == une.loc[10 + HORIZON, "taux_occupation"]
    assert une.loc[10, "taux_il_y_a_1h"] == une.loc[9, "taux_occupation"]


def test_aucune_fuite_de_donnees(historique_demo):
    """Modifier le futur ne doit changer aucune feature du passé."""
    instant = pd.Timestamp("2026-01-20 12:00")
    original = construire_jeu(historique_demo, HORIZON)

    modifie = historique_demo.copy()
    futur = modifie["heure_extraction"] > instant
    modifie.loc[futur, ["taux_occupation", "patients_presents"]] = 99.0
    altere = construire_jeu(modifie, HORIZON)

    colonnes = [c for c in COLONNES_FEATURES if c != "moyenne_installation"]
    avant = lambda jeu: jeu[jeu["heure"] <= instant].set_index(["no_permis", "heure"])[colonnes]  # noqa: E731
    pd.testing.assert_frame_equal(avant(original), avant(altere))


def test_heures_manquantes_deviennent_vides(historique_demo):
    trou = historique_demo.drop(index=[5, 6, 7])         # trois relevés perdus
    jeu = construire_jeu(trou, HORIZON)
    une = jeu[jeu["no_permis"] == "DEMO001"]
    assert len(une) == 24 * 30                           # la grille horaire reste complète
    assert une["taux_occupation"].isna().sum() == 3
