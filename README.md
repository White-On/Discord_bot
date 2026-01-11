# Pybot - Bot Discord

## Description du projet

Pybot est un bot Discord intelligent qui combine les fonctionnalités classiques d'un bot Discord. 

Le bot propose plusieurs fonctionnalités :
- **Sélection aléatoire** : Choisit aléatoirement des membres d'un serveur ou d'un rôle spécifique
- **Gestion de sondages** : Création et analyse de sondages Discord
- **Soirées film** : Organisation automatisée de soirées cinéma avec recherche de synopsis

## Installation

### Prérequis

- Python 3.8 ou supérieur
- Un compte Discord et une application bot
- Clés API pour Discord

### Installation des dépendances

1. Clonez le projet ou téléchargez les fichiers
2. Installez les dépendances requises :

```bash
pip install -r requirements.txt
```

Alternativement, vous pouvez utiliser `pyproject.toml` avec uv:

```bash
uv pip install .
```

et puis :

```bash
uv pip install -r requirements.txt
```

### Configuration

1. Créez un fichier `.env` à la racine du projet
2. Ajoutez vos clés API :

```env
DISCORD_TOKEN=votre_token_discord_bot
```

## Lancement

Pour démarrer le bot, exécutez simplement :

```bash
python main.py
```

Le bot se connectera automatiquement à Discord et synchronisera ses commandes slash.

### Commandes disponibles

- `/random_selector` : Sélectionne aléatoirement un membre ou des membres d'un rôle
- `/poll_decision` : Analyse les résultats d'un sondage terminé
- `/movie_night` : Organise une soirée film avec sondage et synopsis automatiques (les films doivent être séparés par des `|`)

## Développement

Le fichier `Dev.ipynb` contient un notebook Jupyter pour le développement et les tests interactifs du bot.
