# Documentation — MCP Server Template

Bienvenue dans la documentation du template MCP Server. Ce guide est conçu pour les débutants et couvre tout ce dont tu as besoin pour comprendre, configurer et étendre ce serveur.

---

## Table des matières

### Démarrage
1. [Introduction — Qu'est-ce que MCP ?](./01-introduction.md)
   - Le protocole MCP expliqué simplement
   - Ce que fait ce template
   - Vue d'ensemble de l'architecture

2. [Démarrage rapide](./02-demarrage-rapide.md)
   - Prérequis
   - Installation et lancement en 5 minutes
   - Tester que tout fonctionne
   - Comprendre les logs de démarrage

### Développement
3. [Créer des outils (tools)](./03-creer-des-outils.md)
   - Anatomie d'un outil
   - Ajouter un outil à une famille existante
   - Créer une nouvelle famille d'outils
   - Utiliser les utilitaires partagés
   - Ajouter de la traçabilité Langfuse
   - Exemples complets commentés

4. [Configuration](./04-configuration.md)
   - Le fichier `.env` expliqué ligne par ligne
   - Toutes les variables disponibles
   - Valeurs par défaut et cas d'usage

### Sécurité & Infrastructure
5. [Authentification](./05-authentification.md)
   - Mode API Key (recommandé pour débuter)
   - Mode OAuth2 / JWT
   - Mode sans authentification (dev local)
   - Comment tester avec curl

6. [Déploiement et intégrations](./06-deploiement-et-integrations.md)
   - Lancer avec Docker Compose
   - Connecter à Open WebUI
   - Activer l'observabilité Langfuse
   - Développement local avec hot-reload

---

## Parcours recommandé

**Tu découvres MCP pour la première fois ?**
Lis les documents dans l'ordre : 01 → 02 → 03.

**Tu veux juste ajouter un outil rapidement ?**
Va directement au [guide de création d'outils](./03-creer-des-outils.md).

**Tu veux déployer en production ?**
Lis [Configuration](./04-configuration.md), [Authentification](./05-authentification.md) puis [Déploiement](./06-deploiement-et-integrations.md).
