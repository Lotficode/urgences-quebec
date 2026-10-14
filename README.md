# Urgences Québec — prévision de l'achalandage des urgences

Les urgences du Québec débordent, et quand on est malade, on ne sait pas laquelle sera
la moins pleine dans quelques heures. Ce projet collecte chaque heure les données
ouvertes du ministère de la Santé (MSSS), entraîne un modèle de machine learning qui
prévoit le taux d'occupation des civières de chaque urgence 1, 4 et 8 heures à
l'avance, et expose ces prévisions dans une API REST qui recommande l'urgence la
moins achalandée d'une région.

## Fonctionnement

```
 MSSS (CSV horaire)          GitHub Actions               SQLite
┌──────────────────┐ chaque ┌──────────────────┐ ajoute ┌──────────────────┐
│ situation de la  │ heure  │ collecte.py      │──────► │ historique des   │
│ dernière heure   │──────► │ nettoie, valide  │        │ relevés horaires │
└──────────────────┘        └──────────────────┘        └────────┬─────────┘
                                                                 │ chaque lundi
                            ┌──────────────────┐        ┌────────▼─────────┐
   utilisateur ◄─── JSON ───│ API FastAPI      │◄───────│ entrainement.py  │
                            │ prévisions,      │ modèles│ features, modèle,│
                            │ recommandations  │        │ évaluation       │
                            └──────────────────┘        └──────────────────┘
```

1. **Collecte** (`urgences/collecte.py`) : télécharge le relevé horaire, retire les lignes
   de totaux régionaux, convertit les nombres (virgules décimales, valeurs manquantes),
   calcule le taux d'occupation et l'ajoute à SQLite. La clé primaire
   (installation, heure) rend l'import **idempotent** : le relancer ne crée jamais de doublon.
2. **Features** (`urgences/features.py`) : pour chaque urgence et chaque heure, le taux
   actuel, ses valeurs 1, 2, 3, 6, 12, 24 et 168 heures plus tôt, des moyennes mobiles
   sur 24 h et 7 jours, la tendance des 3 dernières heures, le nombre de patients en
   attente, et le calendrier de l'heure visée (heure et jour encodés en sinus/cosinus).
3. **Modèle** (`urgences/modele.py`) : gradient boosting (`HistGradientBoostingRegressor`
   de scikit-learn), plus deux modèles de **régression quantile** (10 % et 90 %) qui
   donnent un intervalle de prévision au lieu d'un seul chiffre.
4. **API** (`urgences/api.py`) : FastAPI, documentation interactive sur `/docs`.

## Choix techniques

- **Pourquoi accumuler l'historique soi-même ?** Le fichier du MSSS ne contient que la
  dernière heure. L'historique n'existe que si on le collecte; c'est le rôle de la collecte horaire,
  qui l'enregistre dans le dépôt toutes les heures (*git scraping*).
- **Validation temporelle.** Le modèle est entraîné sur le passé et testé sur les 20 %
  les plus récents. Les exemples dont la cible tombe dans la période de test sont retirés
  de l'entraînement : aucune information du futur ne fuit dans le modèle
  (`tests/test_features.py::test_aucune_fuite_de_donnees` le vérifie).
- **Deux baselines.** Chaque entraînement compare le modèle à la *persistance*
  (« ce sera comme maintenant ») et à la *baseline saisonnière* (« comme hier à la
  même heure »). Les erreurs sont écrites dans `modeles/metriques.json`.
- **Réentraînement automatique** chaque lundi (`entrainement.yml`) pour suivre
  l'évolution de la saison (grippe, vacances, fermetures).
- **Données manquantes** : une heure sans relevé reste vide dans une grille horaire
  régulière au lieu de décaler toute la série; le gradient boosting gère les valeurs vides.

## Collecte automatique sur le Mac

Le site du MSSS refuse les requêtes venant des serveurs de GitHub (erreur 403) : la
collecte horaire tourne donc sur un Mac personnel, puis pousse les relevés sur GitHub,
où le réentraînement hebdomadaire continue de s'exécuter.

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp scripts/ca.lotficode.urgences-collecte.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/ca.lotficode.urgences-collecte.plist
tail -f /tmp/urgences-collecte.log      # suivre les collectes
```

Le Mac doit être allumé (pas forcément ouvert) pour qu'une heure soit collectée; une
heure manquée reste simplement vide dans la série, ce que le modèle gère.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Utilisation

```bash
python -m urgences.collecte          # ajoute le relevé de la dernière heure
python -m urgences.entrainement      # entraîne les modèles 1 h, 4 h et 8 h
uvicorn urgences.api:app --reload    # API sur http://127.0.0.1:8000/docs
```

L'entraînement exige au moins 7 jours d'historique. Pour essayer le projet tout de
suite, un script génère un historique **fictif** (utilisé aussi par les tests) :

```bash
python scripts/generer_donnees_demo.py --jours 30 --base donnees/demo.db
CHEMIN_BASE=donnees/demo.db python -m urgences.entrainement
CHEMIN_BASE=donnees/demo.db uvicorn urgences.api:app
```

## API

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/sante` | nombre de relevés et date du dernier |
| GET | `/urgences?region=` | situation actuelle de chaque urgence |
| GET | `/urgences/{no_permis}/prevision?horizon=4` | prévision et intervalle 80 % |
| GET | `/recommandations?region=&horizon=4&limite=5` | urgences les moins pleines dans *h* heures |
| GET | `/modele/metriques?horizon=4` | erreurs du modèle et des baselines |

## Tests

```bash
pytest -q
```

14 tests : nettoyage du vrai format du MSSS (point-virgule, encodage Windows, lignes de
totaux), idempotence de l'import, absence de fuite de données, modèle meilleur que la
persistance, refus d'entraîner sur trop peu de données, et toutes les routes de l'API.

## Résultats

À compléter après quelques semaines de collecte réelle, à partir de
`modeles/metriques.json`. Les chiffres obtenus sur l'historique fictif ne mesurent
rien de réel et ne doivent pas être présentés comme des résultats.

## Prochaines étapes

- Ajouter la météo (Environnement Canada) et la saison de la grippe comme features
- Carte interactive des urgences avec la distance depuis la position de l'utilisateur
- Suivi de la dérive : alerte si l'erreur de la semaine dépasse celle de la baseline

## Données

[Fichier horaire des données de la situation à l'urgence](https://www.donneesquebec.ca/recherche/fr/dataset/fichier-horaire-des-donnees-de-la-situation-a-l-urgence),
MSSS, Données Québec, licence CC BY 4.0.

## Auteur

Lotfi Hamed A. — étudiant en génie logiciel, ÉTS Montréal ·
[github.com/Lotficode](https://github.com/Lotficode)
