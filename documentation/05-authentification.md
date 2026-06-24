# Authentification

Le serveur protège l'endpoint MCP (`/mcp`) par authentification. L'endpoint `/health` est toujours public.

---

## Les trois modes

| Mode | Variable `.env` | Usage recommandé |
|---|---|---|
| **API Key** | `AUTH_MODE=api_key` | Production simple, Open WebUI |
| **OAuth2 JWT** | `AUTH_MODE=oauth2` | Intégrations enterprise, multi-tenant |
| **Aucune auth** | `AUTH_MODE=none` | Développement local uniquement |

---

## Mode API Key (recommandé pour débuter)

### Comment ça marche

Chaque requête doit inclure un header `Authorization` avec une clé valide :

```
Authorization: Bearer ma-cle-secrete
```

Le serveur vérifie que la clé est présente dans la liste `API_KEYS`.

### Configuration

```env
AUTH_MODE=api_key
API_KEYS=["sk-prod-abc123", "sk-integration-xyz"]
```

`API_KEYS` est un tableau JSON. Tu peux mettre autant de clés que tu veux — pratique pour donner une clé différente à chaque client ou intégration.

### Bonnes pratiques

- Génère des clés aléatoires longues (`openssl rand -hex 32`)
- Une clé par client/intégration (plus facile à révoquer)
- Ne commite jamais les clés dans git
- Fais pivoter les clés régulièrement

### Tester avec curl

```bash
# Requête valide
curl http://localhost:8000/mcp \
  -H "Authorization: Bearer sk-prod-abc123"

# Requête sans clé → 401
curl http://localhost:8000/mcp

# Requête avec mauvaise clé → 401
curl http://localhost:8000/mcp \
  -H "Authorization: Bearer mauvaise-cle"
```

Réponse en cas d'échec :
```json
{"detail": "Invalid or missing API key"}
```

---

## Mode OAuth2 / JWT (pour les intégrations avancées)

### Comment ça marche

Le client obtient un **JWT (JSON Web Token)** auprès d'un serveur d'identité (ex: Keycloak, Auth0, Okta), puis l'envoie dans le header `Authorization`. Le serveur MCP valide le token en vérifiant sa signature cryptographique via JWKS.

```
┌──────────┐  1. Demande token   ┌─────────────────┐
│  Client  │ ─────────────────>  │  Serveur OAuth2 │
│          │ <─────────────────  │  (Keycloak...)  │
│          │  2. JWT signé        └─────────────────┘
│          │
│          │  3. Requête MCP + JWT   ┌──────────────┐
│          │ ──────────────────────> │  MCP Server  │
│          │ <──────────────────────  │              │
└──────────┘  4. Réponse             └──────────────┘
                                           │
                                    Vérifie signature
                                    via JWKS endpoint
```

### Configuration

```env
AUTH_MODE=oauth2
OAUTH2_JWKS_URL=https://ton-idp.exemple.com/.well-known/jwks.json
OAUTH2_AUDIENCE=https://mon-serveur-mcp
OAUTH2_ISSUER=https://ton-idp.exemple.com
```

> `OAUTH2_JWKS_URL` est **obligatoire** en mode oauth2. Le serveur refuse de démarrer sans cette valeur.

### Ce qui est validé

Pour chaque requête, le serveur vérifie :
1. La **signature** du JWT (via la clé publique JWKS)
2. Le claim **`iss`** (issuer) — doit correspondre à `OAUTH2_ISSUER`
3. Le claim **`aud`** (audience) — doit correspondre à `OAUTH2_AUDIENCE`
4. Le claim **`exp`** (expiration) — le token ne doit pas être expiré

Les clés JWKS sont **mises en cache 1 heure** pour éviter de refaire la requête à chaque appel.

### Tester avec curl (exemple Keycloak)

```bash
# Étape 1 : Obtenir un token
TOKEN=$(curl -s -X POST https://keycloak.exemple.com/realms/mon-realm/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=mon-client" \
  -d "client_secret=mon-secret" \
  | jq -r '.access_token')

# Étape 2 : Appeler le serveur MCP
curl http://localhost:8000/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

---

## Mode sans authentification (`AUTH_MODE=none`)

```env
AUTH_MODE=none
```

**Toutes les requêtes sont acceptées sans vérification.** Un warning apparaît dans les logs au démarrage :

```
WARNING  mcp_server.app: AUTH_MODE=none — authentication is disabled. Do not use in production.
```

Usage : développement local uniquement, pour tester des outils sans avoir à gérer les headers.

```bash
# Plus besoin de header Authorization
curl http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

---

## Comment fonctionne l'auth en interne

L'authentification est implémentée comme un **middleware Starlette** qui intercepte toutes les requêtes avant qu'elles n'atteignent le serveur MCP :

```python
# Simplifié depuis src/mcp_server/auth/dependencies.py

async def require_auth(request: Request) -> None:
    authorization = request.headers.get("Authorization")

    if settings.AUTH_MODE == "api_key":
        await validate_api_key(authorization)    # Vérifie la liste API_KEYS
    elif settings.AUTH_MODE == "oauth2":
        await validate_oauth2(authorization)     # Vérifie le JWT + JWKS
    # AUTH_MODE == "none" : ne fait rien
```

En cas d'échec, une `HTTPException(401)` est levée et le middleware retourne immédiatement :
```json
{"detail": "Invalid or missing API key"}
```

---

## Ajouter un nouveau mode d'authentification

Si tu as besoin d'un mode custom (ex: HMAC, token signé, header custom), voici comment procéder :

### 1. Créer le validateur

```python
# src/mcp_server/auth/hmac_auth.py

import hashlib
import hmac

from fastapi import HTTPException

from mcp_server.config import get_settings


async def validate_hmac(authorization: str | None, body: bytes) -> None:
    """Validate an HMAC-SHA256 signature."""
    settings = get_settings()
    if not authorization or not authorization.startswith("HMAC "):
        raise HTTPException(status_code=401, detail="Missing HMAC signature")

    received_sig = authorization.removeprefix("HMAC ").strip()
    expected_sig = hmac.new(
        settings.HMAC_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
```

### 2. Ajouter le mode dans `config.py`

```python
AUTH_MODE: Literal["api_key", "oauth2", "none", "hmac"] = "api_key"
HMAC_SECRET: str | None = None
```

### 3. Brancher dans `dependencies.py`

```python
from mcp_server.auth.hmac_auth import validate_hmac

async def require_auth(request: Request) -> None:
    # ...
    elif settings.AUTH_MODE == "hmac":
        body = await request.body()
        await validate_hmac(authorization, body)
```
