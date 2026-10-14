#!/bin/bash
# Collecte horaire lancée depuis le Mac (le site du MSSS refuse les serveurs de GitHub),
# puis envoi des nouveaux relevés sur GitHub pour l'entraînement hebdomadaire.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

git pull --rebase --quiet origin main
python -m urgences.collecte

git add donnees/urgences.db
if ! git diff --cached --quiet; then
    git commit --quiet -m "Relevé $(date -u +'%Y-%m-%d %H:00') UTC"
    git push --quiet origin main
fi
