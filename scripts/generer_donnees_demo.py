"""Génère un historique FICTIF pour tester le projet avant d'avoir collecté de vraies données.

Les chiffres sont inventés (cycle jour/nuit, cycle de la semaine, bruit aléatoire).
Ils servent uniquement aux tests et à la démo : les résultats du README doivent
venir des vraies données collectées, jamais de ce script.

    python scripts/generer_donnees_demo.py --jours 30
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from urgences import base  # noqa: E402

URGENCES_FICTIVES = [
    ("DEMO001", "Montréal", "Hôpital Démo A", 40, 1.10),
    ("DEMO002", "Montréal", "Hôpital Démo B", 28, 0.95),
    ("DEMO003", "Laval", "Hôpital Démo C", 32, 1.25),
    ("DEMO004", "Montérégie", "Hôpital Démo D", 24, 0.80),
    ("DEMO005", "Capitale-Nationale", "Hôpital Démo E", 36, 1.05),
]


def generer(jours: int = 30, graine: int = 0) -> pd.DataFrame:
    aleatoire = np.random.default_rng(graine)
    heures = pd.date_range("2026-01-05", periods=24 * jours, freq="h")
    lignes = []
    for permis, region, nom, civieres, niveau in URGENCES_FICTIVES:
        derive = 0.0
        for heure in heures:
            # Plus plein en fin de journée, moins la nuit; plus plein le lundi.
            cycle_jour = 0.25 * np.sin(2 * np.pi * (heure.hour - 10) / 24)
            cycle_semaine = 0.10 if heure.dayofweek == 0 else (-0.05 if heure.dayofweek >= 5 else 0)
            derive = 0.9 * derive + aleatoire.normal(0, 0.04)    # inertie d'une heure à l'autre
            taux = max(0.2, niveau + cycle_jour + cycle_semaine + derive)
            occupees = int(round(taux * civieres))
            lignes.append({
                "no_permis": permis, "heure_extraction": heure.strftime("%Y-%m-%dT%H:%M:%S"),
                "region": region, "nom_etablissement": "CISSS Démo", "nom_installation": nom,
                "civieres_fonctionnelles": civieres, "civieres_occupees": occupees,
                "patients_plus_24h": int(occupees * 0.3), "patients_plus_48h": int(occupees * 0.1),
                "patients_presents": int(occupees * 1.8), "patients_attente_pec": int(occupees * 0.5),
                "dms_civiere": 20.0, "dms_ambulatoire": 5.0,
                "taux_occupation": round(occupees / civieres, 4),
            })
    return pd.DataFrame(lignes)


if __name__ == "__main__":
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--jours", type=int, default=30)
    parseur.add_argument("--base", default="donnees/demo.db")
    arguments = parseur.parse_args()
    with base.connecter(arguments.base) as connexion:
        print(base.enregistrer(connexion, generer(arguments.jours)), "relevés fictifs dans", arguments.base)
