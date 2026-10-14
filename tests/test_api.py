import pytest
from fastapi.testclient import TestClient

from urgences import base, config, modele
from urgences.api import creer_app


@pytest.fixture
def client(base_demo, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DOSSIER_MODELES", tmp_path / "modeles")
    with base.connecter(base_demo) as connexion:
        historique = base.lire_historique(connexion)
    modele.sauvegarder(modele.entrainer(historique, horizon=4))
    return TestClient(creer_app(base_demo))


def test_sante(client):
    reponse = client.get("/sante").json()
    assert reponse["statut"] == "ok" and reponse["releves"] == 5 * 24 * 30


def test_situation_actuelle_filtree_par_region(client):
    urgences = client.get("/urgences", params={"region": "montréal"}).json()
    assert {u["no_permis"] for u in urgences} == {"DEMO001", "DEMO002"}


def test_recommandations_triees(client):
    recos = client.get("/recommandations", params={"horizon": 4, "limite": 3}).json()
    assert len(recos) == 3
    taux = [r["taux_prevu"] for r in recos]
    assert taux == sorted(taux)


def test_prevision_et_erreurs(client):
    assert client.get("/urgences/DEMO003/prevision", params={"horizon": 4}).status_code == 200
    assert client.get("/urgences/INCONNU/prevision", params={"horizon": 4}).status_code == 404
    assert client.get("/urgences/DEMO003/prevision", params={"horizon": 8}).status_code == 503
