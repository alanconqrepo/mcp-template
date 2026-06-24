# Introduction — Qu'est-ce que MCP ?

## Le protocole MCP en deux mots

**MCP** (Model Context Protocol) est un protocole open-source créé par Anthropic qui définit comment un modèle de langage (LLM) peut appeler des **outils externes** de manière standardisée.

Concrètement : tu écris une fonction Python, tu la déclares comme "outil MCP", et n'importe quel LLM compatible (Claude, GPT via Open WebUI, etc.) peut l'appeler comme s'il utilisait une API.

```
┌─────────────────┐        MCP / HTTP         ┌──────────────────────┐
│   LLM / Client  │  ──────────────────────>  │  Ton serveur MCP     │
│ (Open WebUI,    │  <──────────────────────  │  (ce template)       │
│  Claude, etc.)  │      JSON-RPC 2.0         │                      │
└─────────────────┘                           └──────────────────────┘
```

### Pourquoi MCP plutôt qu'une API classique ?

Une API classique, c'est toi qui décides quand l'appeler dans ton code. Avec MCP, **c'est le LLM qui décide** quand utiliser l'outil selon le contexte de la conversation. Tu décris ce que fait l'outil en langage naturel, et le modèle s'en charge.

Exemples d'outils utiles :
- Rechercher dans une base de données
- Lire/écrire des fichiers
- Appeler une API externe (météo, CRM, ERP...)
- Exécuter des calculs complexes
- Envoyer des emails ou des notifications

---

## Ce que fait ce template

Ce repository est un **point de départ prêt à l'emploi** pour créer ton propre serveur MCP. Il te fournit :

- La plomberie complète (transport HTTP, auth, config, logs)
- Une structure claire pour organiser tes outils
- Deux outils d'exemple fonctionnels (`ping` et `text_summary`)
- Docker Compose pour déployer en une commande
- Une connexion directe à Open WebUI

Tu n'as qu'à **ajouter tes propres outils** — tout le reste est déjà géré.

---

## Vue d'ensemble de l'architecture

```
mcp-server-template/
│
├── src/mcp_server/
│   │
│   ├── app.py          ← Point d'entrée FastAPI + montage du serveur MCP
│   ├── config.py       ← Toute la configuration (variables d'environnement)
│   ├── server.py       ← Instance FastMCP partagée par tous les outils
│   │
│   ├── auth/           ← Authentification (API key ou OAuth2 JWT)
│   │
│   ├── tools/          ← Tes outils MCP, organisés par famille
│   │   ├── system/     ← Famille "system" : ping, diagnostics...
│   │   └── text/       ← Famille "text" : résumé, comptage...
│   │
│   ├── utils/          ← Fonctions utilitaires pures (texte, dates...)
│   │
│   └── observability/  ← Traçabilité avec Langfuse
│
└── tests/              ← Tests automatisés
```

### Le flux d'une requête

Voici ce qui se passe quand un LLM appelle l'outil `ping` :

```
1. Le LLM envoie une requête HTTP POST à /mcp
   avec {"method": "tools/call", "params": {"name": "ping"}}

2. AuthMiddleware vérifie le header Authorization

3. FastMCP reçoit la requête et cherche l'outil "ping"

4. La fonction ping() s'exécute en Python

5. La réponse {"message": "pong", "timestamp": "..."} est renvoyée au LLM

6. Le LLM intègre le résultat dans sa réponse
```

### Les composants clés

| Composant | Rôle |
|---|---|
| **FastMCP** | Framework qui gère le protocole MCP |
| **FastAPI** | Serveur web qui expose le point d'entrée HTTP |
| **Pydantic Settings** | Lit et valide la configuration depuis `.env` |
| **uvicorn** | Serveur ASGI qui fait tourner le tout |

---

## Transport : Streamable HTTP

Ce template utilise le transport **Streamable HTTP** (le plus moderne). Cela signifie que la communication entre le LLM et le serveur se fait via de simples requêtes HTTP POST avec des réponses JSON-RPC. C'est compatible avec n'importe quel client HTTP, facile à déboguer avec `curl`, et déployable derrière n'importe quel reverse proxy.

L'endpoint MCP est accessible à : `http://ton-serveur:8000/mcp`
