# Configuration

Toute la configuration du serveur se fait via des variables d'environnement, lues depuis le fichier `.env` au démarrage. Aucune valeur n'est hardcodée dans le code.

---

## Le fichier `.env`

Le fichier `.env.example` à la racine du projet contient toutes les variables disponibles avec des commentaires. **Ne commite jamais ton `.env`** — il contient tes clés secrètes. Le `.gitignore` l'exclut déjà.

```bash
cp .env.example .env
# Puis édite .env avec ton éditeur
```

---

## Référence complète des variables

### Serveur HTTP

| Variable | Défaut | Description |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Adresse d'écoute. `0.0.0.0` = toutes les interfaces (Docker). |
| `SERVER_PORT` | `8000` | Port d'écoute. Mappé dans `docker-compose.yml`. |
| `LOG_LEVEL` | `info` | Verbosité des logs : `debug`, `info`, `warning`, `error`. |

**Exemple :**
```env
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
LOG_LEVEL=debug
```

---

### Serveur MCP

| Variable | Défaut | Description |
|---|---|---|
| `MCP_SERVER_NAME` | `mcp-server-template` | Nom affiché dans les logs et renvoyé lors du handshake MCP. |
| `MCP_MOUNT_PATH` | `/mcp` | Chemin URL de l'endpoint MCP. |

**Exemple :**
```env
MCP_SERVER_NAME=mon-assistant-meteo
MCP_MOUNT_PATH=/mcp
```

> `MCP_MOUNT_PATH` doit correspondre à l'URL configurée dans Open WebUI. Si tu changes ce chemin, mets à jour ta config Open WebUI en conséquence.

---

### Authentification

| Variable | Défaut | Description |
|---|---|---|
| `AUTH_MODE` | `api_key` | Mode d'auth : `api_key`, `oauth2`, ou `none`. |
| `API_KEYS` | `[]` | JSON array de clés valides (mode `api_key`). |
| `OAUTH2_TOKEN_URL` | — | URL du endpoint de token OAuth2 (informatif, non utilisé par le serveur). |
| `OAUTH2_JWKS_URL` | — | **Requis** en mode `oauth2`. URL de la clé publique JWKS. |
| `OAUTH2_AUDIENCE` | — | Valeur attendue du claim `aud` dans le JWT. |
| `OAUTH2_ISSUER` | — | Valeur attendue du claim `iss` dans le JWT. |

**Exemples :**

Mode API Key (le plus simple) :
```env
AUTH_MODE=api_key
API_KEYS=["sk-prod-abc123", "sk-client-xyz456"]
```

Mode OAuth2 :
```env
AUTH_MODE=oauth2
OAUTH2_JWKS_URL=https://ton-idp.exemple.com/.well-known/jwks.json
OAUTH2_AUDIENCE=https://mon-serveur-mcp
OAUTH2_ISSUER=https://ton-idp.exemple.com
```

Désactiver l'auth (dev local uniquement) :
```env
AUTH_MODE=none
```

Pour plus de détails, voir [Authentification](./05-authentification.md).

---

### CORS

| Variable | Défaut | Description |
|---|---|---|
| `CORS_ORIGINS` | `[]` | JSON array d'origines autorisées. Vide = CORS désactivé. |

**Exemple :**
```env
# Autoriser Open WebUI et un frontend local
CORS_ORIGINS=["https://mon-open-webui.exemple.com", "http://localhost:3000"]
```

> CORS n'est nécessaire que si un navigateur web appelle directement ton API. Pour Open WebUI (appel serveur→serveur), CORS n'est pas nécessaire.

---

### Langfuse (observabilité)

| Variable | Défaut | Description |
|---|---|---|
| `LANGFUSE_ENABLED` | `false` | Active/désactive la traçabilité. |
| `LANGFUSE_SECRET_KEY` | — | Clé secrète Langfuse (commence par `sk-lf-...`). |
| `LANGFUSE_PUBLIC_KEY` | — | Clé publique Langfuse (commence par `pk-lf-...`). |
| `LANGFUSE_HOST` | — | URL de ton instance Langfuse. |

**Exemple avec Langfuse Cloud :**
```env
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-abcdef...
LANGFUSE_PUBLIC_KEY=pk-lf-abcdef...
LANGFUSE_HOST=https://cloud.langfuse.com
```

**Exemple avec Langfuse self-hosted :**
```env
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-abcdef...
LANGFUSE_PUBLIC_KEY=pk-lf-abcdef...
LANGFUSE_HOST=http://langfuse:3000
```

> Si `LANGFUSE_ENABLED=true` mais que les clés sont manquantes, le serveur démarre quand même avec un warning. Langfuse ne fait jamais crasher le serveur.

---

## Accéder à la configuration dans le code

Si tu as besoin de lire une valeur de configuration dans un outil ou un utilitaire, utilise `get_settings()` :

```python
from mcp_server.config import get_settings

settings = get_settings()
print(settings.MCP_SERVER_NAME)  # → "mon-serveur"
print(settings.AUTH_MODE)         # → "api_key"
```

> `get_settings()` est mis en cache (singleton). La valeur est lue une seule fois au démarrage.

### Ajouter une nouvelle variable de configuration

1. Ajoute le champ dans `src/mcp_server/config.py` :

```python
class Settings(BaseSettings):
    # ... champs existants ...

    # Ma nouvelle config
    OPENAI_API_KEY: str | None = None
    MAX_RESULTS: int = 50
    ENABLE_CACHE: bool = True
```

2. Ajoute la variable dans `.env.example` avec un commentaire :

```env
# ── OpenAI ────────────────────────────────────────────
OPENAI_API_KEY=sk-...          # Clé API OpenAI
MAX_RESULTS=50                 # Nombre maximum de résultats renvoyés
ENABLE_CACHE=true              # Activer le cache en mémoire
```

3. Utilise-la dans ton code :

```python
from mcp_server.config import get_settings

@mcp.tool(description="Search using OpenAI.")
async def search(query: str) -> dict:
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY
    max_results = settings.MAX_RESULTS
    # ...
```

---

## Validation au démarrage

Certaines configurations invalides font crasher le serveur au démarrage avec un message d'erreur clair. C'est voulu — mieux vaut échouer vite que de démarrer avec une config incorrecte.

Exemple : si `AUTH_MODE=oauth2` mais `OAUTH2_JWKS_URL` n'est pas défini :
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, OAUTH2_JWKS_URL is required when AUTH_MODE=oauth2
```

Tu peux ajouter tes propres validations dans `config.py` en utilisant `@model_validator` :

```python
from pydantic import model_validator

class Settings(BaseSettings):
    OPENAI_API_KEY: str | None = None
    ENABLE_AI_FEATURES: bool = False

    @model_validator(mode="after")
    def check_ai_config(self) -> "Settings":
        if self.ENABLE_AI_FEATURES and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY est requis quand ENABLE_AI_FEATURES=true")
        return self
```
