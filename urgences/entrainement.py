"""Réentraîne un modèle par horizon et enregistre ses métriques.

    python -m urgences.entrainement            # horizons 1 h, 4 h et 8 h
    python -m urgences.entrainement --horizons 4
"""
import argparse
import json

from urgences import base, config, modele


def entrainer_tout(horizons=config.HORIZONS, chemin_base=None) -> dict:
    with base.connecter(chemin_base) as connexion:
        historique = base.lire_historique(connexion)

    rapport = {}
    for horizon in horizons:
        try:
            nouveau = modele.entrainer(historique, horizon)
        except modele.DonneesInsuffisantes as erreur:
            print(f"[{horizon} h] {erreur}")
            continue
        modele.sauvegarder(nouveau)
        rapport[f"{horizon}h"] = nouveau.metriques
        m = nouveau.metriques
        print(
            f"[{horizon} h] erreur moyenne : modèle {m['mae_modele']} pts | "
            f"persistance {m['mae_persistance']} pts | saisonnière {m['mae_saisonniere']} pts"
        )

    if rapport:
        config.DOSSIER_MODELES.mkdir(parents=True, exist_ok=True)
        (config.DOSSIER_MODELES / "metriques.json").write_text(
            json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return rapport


if __name__ == "__main__":
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--horizons", type=int, nargs="+", default=list(config.HORIZONS))
    entrainer_tout(parseur.parse_args().horizons)
