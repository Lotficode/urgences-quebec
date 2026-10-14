"""Collecte : télécharge le relevé horaire officiel, le nettoie et l'ajoute à l'historique.

À lancer une fois par heure (tâche planifiée cron ou GitHub Actions) :
    python -m urgences.collecte
"""
import io
import re
import unicodedata

import pandas as pd
import requests

from urgences import base, config

# Nom normalisé de la colonne du MSSS -> nom de notre table.
# On compare des débuts de noms, car le gouvernement change parfois un pluriel
# (civiere / civieres) ou un accent d'un fichier à l'autre.
CORRESPONDANCES = [
    ("region", "region"),
    ("nom_etablissement", "nom_etablissement"),
    ("nom_installation", "nom_installation"),
    ("no_permis_installation", "no_permis"),
    ("nombre_de_civieres_fonctionnelles", "civieres_fonctionnelles"),
    ("nombre_de_civieres_occupees", "civieres_occupees"),
    ("nombre_de_patients_sur_civiere", "patients_plus_24h"),  # précisé plus bas (24 vs 48)
    ("nombre_total_de_patients_presents", "patients_presents"),
    ("nombre_total_de_patients_en_attente", "patients_attente_pec"),
    ("dms_sur_civiere", "dms_civiere"),
    ("dms_ambulatoire", "dms_ambulatoire"),
    ("heure_de_l", "heure_extraction"),
]

ENTIERS = [
    "civieres_fonctionnelles", "civieres_occupees", "patients_plus_24h",
    "patients_plus_48h", "patients_presents", "patients_attente_pec",
]
DECIMAUX = ["dms_civiere", "dms_ambulatoire"]


def normaliser_nom(nom: str) -> str:
    """'Heure_de_l’extraction_(image)' -> 'heure_de_l_extraction_image'."""
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sans_accents.lower()).strip("_")


def renommer_colonnes(brut: pd.DataFrame) -> pd.DataFrame:
    renommage = {}
    for colonne in brut.columns:
        nom = normaliser_nom(colonne)
        if nom.endswith("_horaire"):          # DMS au format hh:mm, doublon du format décimal
            continue
        for prefixe, cible in CORRESPONDANCES:
            if nom.startswith(prefixe):
                if cible == "patients_plus_24h" and "48" in nom:
                    cible = "patients_plus_48h"
                renommage[colonne] = cible
                break
    return brut.rename(columns=renommage)[list(dict.fromkeys(renommage.values()))]


def en_nombre(serie: pd.Series) -> pd.Series:
    """Accepte '3,5', '3.5', '', 'N/D' : tout ce qui n'est pas un nombre devient vide."""
    texte = serie.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(texte, errors="coerce")


def lire_csv(contenu: bytes) -> pd.DataFrame:
    for encodage in ("utf-8-sig", "cp1252"):
        try:
            texte = contenu.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    # sep=None : pandas devine le séparateur (virgule ou point-virgule).
    return pd.read_csv(io.StringIO(texte), sep=None, engine="python", dtype=str)


def nettoyer(brut: pd.DataFrame) -> pd.DataFrame:
    releves = renommer_colonnes(brut)

    # Le fichier contient aussi des lignes « Total régional » et « Ensemble du Québec » :
    # on ne garde que les vraies installations, qui ont un numéro de permis.
    releves = releves[releves["no_permis"].fillna("").str.strip() != ""].copy()
    releves["no_permis"] = releves["no_permis"].str.strip()

    for colonne in ENTIERS + DECIMAUX:
        if colonne not in releves:
            releves[colonne] = None
        releves[colonne] = en_nombre(releves[colonne])
    for colonne in ("region", "nom_etablissement", "nom_installation"):
        if colonne not in releves:
            releves[colonne] = None

    # Heure du relevé arrondie à l'heure : une série régulière par urgence.
    heures = pd.to_datetime(releves["heure_extraction"], errors="coerce", format="mixed")
    releves["heure_extraction"] = heures.dt.floor("h").dt.strftime("%Y-%m-%dT%H:%M:%S")
    releves = releves.dropna(subset=["heure_extraction"])

    fonctionnelles = releves["civieres_fonctionnelles"].where(releves["civieres_fonctionnelles"] > 0)
    releves["taux_occupation"] = (releves["civieres_occupees"] / fonctionnelles).round(4)
    return releves[base.COLONNES].reset_index(drop=True)


def telecharger(url: str = config.URL_RELEVE) -> bytes:
    reponse = requests.get(url, timeout=60, headers={"User-Agent": "urgences-quebec/1.0"})
    reponse.raise_for_status()
    return reponse.content


def collecter(url: str = config.URL_RELEVE, chemin_base=None) -> int:
    releves = nettoyer(lire_csv(telecharger(url)))
    with base.connecter(chemin_base) as connexion:
        ajoutes = base.enregistrer(connexion, releves)
    return ajoutes


if __name__ == "__main__":
    nombre = collecter()
    print(f"{nombre} nouveaux relevés enregistrés dans {config.CHEMIN_BASE}")
