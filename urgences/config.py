"""Paramètres du projet, lus depuis les variables d'environnement quand elles existent."""
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Fichier horaire officiel du MSSS (Données Québec), mis à jour chaque heure.
URL_RELEVE = os.getenv(
    "URL_RELEVE",
    "https://www.msss.gouv.qc.ca/professionnels/statistiques/documents/urgences/"
    "Releve_horaire_urgences_7jours_nbpers.csv",
)

CHEMIN_BASE = Path(os.getenv("CHEMIN_BASE", RACINE / "donnees" / "urgences.db"))
DOSSIER_MODELES = Path(os.getenv("DOSSIER_MODELES", RACINE / "modeles"))

# Horizons de prévision proposés par défaut, en heures.
HORIZONS = (1, 4, 8)
