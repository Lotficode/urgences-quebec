import pytest

from urgences import modele


def test_bat_la_baseline_de_persistance(historique_demo):
    entraine = modele.entrainer(historique_demo, horizon=4)
    m = entraine.metriques
    assert m["mae_modele"] < m["mae_persistance"]
    assert m["installations"] == 5
    assert 0.5 < m["couverture_intervalle_80"] <= 1


def test_refuse_un_historique_trop_court(historique_demo):
    trois_jours = historique_demo[historique_demo["heure_extraction"] < "2026-01-08"]
    with pytest.raises(modele.DonneesInsuffisantes):
        modele.entrainer(trois_jours, horizon=4)


def test_prediction_une_ligne_par_urgence(historique_demo):
    entraine = modele.entrainer(historique_demo, horizon=1)
    previsions = modele.predire(entraine, historique_demo)
    assert len(previsions) == 5
    assert (previsions["taux_bas"] <= previsions["taux_haut"]).all()
    assert (previsions["heure_visee"] - previsions["heure"]).dt.total_seconds().eq(3600).all()
