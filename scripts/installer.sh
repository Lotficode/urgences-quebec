#!/bin/bash
# Installe la collecte horaire sur le Mac, en une commande : bash scripts/installer.sh
set -e
cd "$(dirname "$0")/.."
echo "== 1/5 Nettoyage des verrous Git"
rm -f .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock

echo "== 2/5 Environnement Python et librairies (1-2 min)"
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "== 3/5 Premier relevé"
python -m urgences.collecte

echo "== 4/5 Envoi sur GitHub"
git add -A
git commit --quiet -m "Collecte locale planifiée (le MSSS bloque les serveurs GitHub) + premier relevé" || true
git pull --rebase --quiet origin main
git push --quiet origin main

echo "== 5/5 Collecte automatique chaque heure (xx h 55)"
mkdir -p ~/Library/LaunchAgents
cp scripts/ca.lotficode.urgences-collecte.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/ca.lotficode.urgences-collecte.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/ca.lotficode.urgences-collecte.plist

echo ""
echo "Terminé. La collecte tourne chaque heure tant que le Mac est allumé."
echo "Suivi : tail -f /tmp/urgences-collecte.log"
