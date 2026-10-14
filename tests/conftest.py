import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generer_donnees_demo import generer  # noqa: E402
from urgences import base  # noqa: E402

DOSSIER = Path(__file__).resolve().parent


@pytest.fixture
def csv_officiel() -> bytes:
    return (DOSSIER / "releve_exemple.csv").read_bytes()


@pytest.fixture(scope="session")
def historique_demo():
    historique = generer(jours=30)
    historique["heure_extraction"] = historique["heure_extraction"].astype("datetime64[ns]")
    return historique


@pytest.fixture
def base_demo(tmp_path):
    chemin = tmp_path / "demo.db"
    with base.connecter(chemin) as connexion:
        base.enregistrer(connexion, generer(jours=30))
    return chemin
