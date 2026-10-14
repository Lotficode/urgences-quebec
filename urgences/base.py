"""Stockage de l'historique des relevés dans SQLite.

Le fichier du gouvernement ne contient que la situation de la dernière heure :
l'historique n'existe que si on l'accumule nous-mêmes, heure après heure.
"""
import sqlite3
from pathlib import Path

import pandas as pd

from urgences import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS releves (
    no_permis            TEXT    NOT NULL,
    heure_extraction     TEXT    NOT NULL,   -- ISO 8601, heure du relevé
    region               TEXT,
    nom_etablissement    TEXT,
    nom_installation     TEXT,
    civieres_fonctionnelles INTEGER,
    civieres_occupees    INTEGER,
    patients_plus_24h    INTEGER,
    patients_plus_48h    INTEGER,
    patients_presents    INTEGER,
    patients_attente_pec INTEGER,
    dms_civiere          REAL,
    dms_ambulatoire      REAL,
    taux_occupation      REAL,               -- civières occupées / fonctionnelles
    PRIMARY KEY (no_permis, heure_extraction)
);
CREATE INDEX IF NOT EXISTS idx_releves_heure ON releves (heure_extraction);
"""

COLONNES = [
    "no_permis", "heure_extraction", "region", "nom_etablissement", "nom_installation",
    "civieres_fonctionnelles", "civieres_occupees", "patients_plus_24h", "patients_plus_48h",
    "patients_presents", "patients_attente_pec", "dms_civiere", "dms_ambulatoire",
    "taux_occupation",
]


def connecter(chemin: Path | str | None = None) -> sqlite3.Connection:
    chemin = Path(chemin or config.CHEMIN_BASE)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    connexion = sqlite3.connect(chemin)
    connexion.executescript(SCHEMA)
    return connexion


def enregistrer(connexion: sqlite3.Connection, releves: pd.DataFrame) -> int:
    """Insère les relevés; un relevé déjà présent (même installation, même heure) est ignoré.

    Retourne le nombre de lignes réellement ajoutées. Relancer la collecte deux fois
    pour la même heure ne crée donc jamais de doublon (import idempotent).
    """
    avant = connexion.total_changes
    lignes = releves[COLONNES].astype(object).where(releves[COLONNES].notna(), None)
    connexion.executemany(
        f"INSERT OR IGNORE INTO releves ({', '.join(COLONNES)}) "
        f"VALUES ({', '.join('?' for _ in COLONNES)})",
        lignes.itertuples(index=False, name=None),
    )
    connexion.commit()
    return connexion.total_changes - avant


def lire_historique(connexion: sqlite3.Connection) -> pd.DataFrame:
    historique = pd.read_sql_query(
        "SELECT * FROM releves ORDER BY no_permis, heure_extraction", connexion
    )
    historique["heure_extraction"] = pd.to_datetime(historique["heure_extraction"])
    return historique


def dernier_releve(connexion: sqlite3.Connection) -> pd.DataFrame:
    """La situation la plus récente de chaque urgence."""
    return pd.read_sql_query(
        """
        SELECT r.* FROM releves r
        JOIN (SELECT no_permis, MAX(heure_extraction) AS h FROM releves GROUP BY no_permis) d
          ON r.no_permis = d.no_permis AND r.heure_extraction = d.h
        ORDER BY r.region, r.nom_installation
        """,
        connexion,
    )
