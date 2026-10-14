#!/bin/bash
# Tâche lancée chaque heure par macOS (launchd) :
#   - chaque heure : ajoute le relevé du MSSS à donnees/urgences.db
#   - le lundi à 6 h : réentraîne les modèles sur tout l'historique
# Tout reste sur le Mac : pas de serveur, pas de push automatique.
cd "$(dirname "$0")/.."
PYTHON=.venv/bin/python

echo "--- $(date '+%Y-%m-%d %H:%M')"
$PYTHON -m urgences.collecte

if [ "$(date +%u)" = "1" ] && [ "$(date +%H)" = "06" ]; then
    $PYTHON -m urgences.entrainement
fi
