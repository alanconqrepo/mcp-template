# Démarrage rapide

## Prérequis

- **Docker** et **Docker Compose** installés ([installer Docker](https://docs.docker.com/get-docker/))
- `curl` ou un client HTTP pour tester
- 5 minutes

> Si tu veux développer sans Docker (pour modifier le code en direct), tu auras besoin de Python 3.12+ et de `uv`. Voir la section [Développement local](#développement-local-sans-docker).

---

## Lancement en 5 minutes

### 1. Cloner le repository

```bash
git clone <url-du-repo> mon-mcp-server
cd mon-mcp-server
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
```

Ouvre `.env` et modifie au minimum ces deux lignes :

```env
MCP_SERVER_NAME=mon-serveur          # Donne un nom à ton serveur
API_KEYS=["ma-cle-secrete-1"]        # Ta clé API (invente une chaîne)
```

> Pour l'instant, laisse tout le reste par défaut. Tu pourras ajuster plus tard.

### 3. Démarrer le serveur

```bash
docker compose up --build
```

La première fois, Docker télécharge les images et installe les dépendances (~1-2 minutes). Les fois suivantes, le démarrage prend quelques secondes.

Tu dois voir dans les logs :

```
mcp-server  | INFO:     MCP Server 'mon-serveur' starting
mcp-server  |   Transport: Streamable HTTP
mcp-server  |   Mount path: /mcp
mcp-server  |   Auth mode: api_key
mcp-server  |   Tools loaded: ping, text_summary
mcp-server  |   Langfuse: disabled
mcp-server  | INFO:     Application startup complete.
mcp-server  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Vérifier que tout fonctionne

### Test 1 : Le health check (sans authentification)

```bash
curl http://localhost:8000/health
```

Réponse attendue :
```json
{
  "status": "ok",
  "server_name": "mon-serveur",
  "auth_mode": "api_key",
  "tools_count": 2,
  "langfuse_enabled": false
}
```

### Test 2 : Lister les outils disponibles

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer ma-cle-secrete-1" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

Note le `mcp-session-id` dans les headers de la réponse, puis :

```bash
# Remplace TON_SESSION_ID par la valeur reçue
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer ma-cle-secrete-1" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: TON_SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

### Test 3 : Appeler l'outil ping

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer ma-cle-secrete-1" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: TON_SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ping","arguments":{}}}'
```

Réponse attendue (format SSE) :
```
event: message
data: {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"message\": \"pong\", \"timestamp\": \"2026-06-24T...Z\"}"}]}}
```

### Test 4 : Vérifier que l'auth fonctionne

```bash
# Sans clé → doit retourner 401
curl http://localhost:8000/mcp
# {"detail":"Invalid or missing API key"}
```

---

## Comprendre les logs de démarrage

```
MCP Server 'mon-serveur' starting
  Transport: Streamable HTTP       ← Protocole de communication utilisé
  Mount path: /mcp                 ← URL de l'endpoint MCP
  Auth mode: api_key               ← Mode d'authentification actif
  Tools loaded: ping, text_summary ← Outils découverts et enregistrés
  Langfuse: disabled               ← Observabilité désactivée (pas de credentials)
```

Si tu vois `Tools loaded: none`, c'est que l'auto-découverte a échoué. Vérifie que tes fichiers `__init__.py` importent bien tes modules d'outils.

---

## Développement local (sans Docker)

Pour modifier le code et voir les changements en direct :

### Installer les dépendances

```bash
# Installer uv si pas déjà fait
pip install uv

# Installer le projet en mode dev
uv pip install -e ".[dev]"
```

### Créer un fichier .env local

```bash
cp .env.example .env
# Éditez .env selon vos besoins
```

### Lancer le serveur avec hot-reload

```bash
AUTH_MODE=none uvicorn mcp_server.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --app-dir src
```

> `AUTH_MODE=none` désactive l'authentification pour simplifier le développement local. Ne jamais utiliser en production.

### Lancer les tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

---

## Structure du fichier `.env`

Voici les variables les plus importantes à connaître dès le début :

```env
# Nom affiché dans les logs et dans Open WebUI
MCP_SERVER_NAME=mon-serveur

# Clés API valides (JSON array)
API_KEYS=["cle-1", "cle-2"]

# URL où le serveur MCP écoute
MCP_MOUNT_PATH=/mcp

# Désactiver l'auth pour le dev local uniquement
# AUTH_MODE=none
```

Pour la référence complète de toutes les variables, consulte [Configuration](./04-configuration.md).
