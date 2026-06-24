# Déploiement et intégrations

---

## Docker Compose (production)

### Démarrer le serveur

```bash
# Construire et démarrer en arrière-plan
docker compose up -d --build

# Voir les logs en direct
docker compose logs -f mcp-server

# Arrêter le serveur
docker compose down
```

### Configuration `docker-compose.yml`

```yaml
services:
  mcp-server:
    build: .
    ports:
      - "${SERVER_PORT:-8000}:8000"   # Port configurable via .env
    env_file: .env                     # Toutes les variables depuis .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped            # Redémarre automatiquement en cas de crash
```

### Vérifier l'état de santé

```bash
# Voir l'état du healthcheck Docker
docker compose ps

# Appel direct au endpoint de santé
curl http://localhost:8000/health
```

---

## Développement local avec hot-reload

Crée un fichier `docker-compose.override.yml` (ignoré par git) pour surcharger la config en dev :

```yaml
# docker-compose.override.yml
services:
  mcp-server:
    volumes:
      - ./src:/app/src    # Monte le code source en live
    command: >
      uvicorn mcp_server.app:app
      --host 0.0.0.0
      --port 8000
      --reload
      --app-dir src
    environment:
      AUTH_MODE: none      # Désactive l'auth en dev
      LOG_LEVEL: debug
```

```bash
docker compose up  # Prend automatiquement l'override en compte
```

Maintenant, chaque modification dans `src/` redémarre automatiquement le serveur.

---

## Intégration avec Open WebUI

Open WebUI peut appeler n'importe quel serveur MCP compatible Streamable HTTP.

### Configuration dans Open WebUI

Dans l'interface Open WebUI, va dans **Settings → Tools → Add MCP Server** et renseigne :

| Champ | Valeur |
|---|---|
| **Name** | Mon serveur MCP |
| **URL** | `http://mcp-server:8000/mcp` (même réseau Docker) |
| **Transport** | Streamable HTTP |
| **Authorization** | `Bearer ta-cle-api` |

Si Open WebUI et le serveur MCP sont sur la **même machine mais pas dans le même réseau Docker**, utilise `http://localhost:8000/mcp`.

### Même réseau Docker que Open WebUI

Si Open WebUI tourne déjà dans Docker, il faut que les deux services partagent le même réseau :

```yaml
# docker-compose.override.yml
services:
  mcp-server:
    networks:
      - webui_network    # Remplace par le nom du réseau Open WebUI

networks:
  webui_network:
    external: true
```

Pour trouver le nom du réseau Open WebUI :
```bash
docker network ls | grep webui
```

### Tester la connexion depuis Open WebUI

1. Dans Open WebUI, ouvre une nouvelle conversation
2. Clique sur le bouton **Tools** (icône clé)
3. Ton serveur MCP doit apparaître avec ses outils listés
4. Envoie un message comme : *"Peux-tu faire un ping ?"* — le LLM devrait appeler l'outil `ping`

---

## Observabilité avec Langfuse

Langfuse te permet de tracer et analyser tous les appels à tes outils.

### Activer Langfuse

```env
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Ce qui est tracé automatiquement

Pour chaque appel d'outil, Langfuse enregistre :
- Le nom de l'outil appelé
- Les inputs (via `trace_tool("nom", inputs={...})`)
- La durée d'exécution en millisecondes
- Le statut (succès ou erreur)
- Le message d'erreur en cas d'exception

### Voir les traces dans Langfuse

Une fois les credentials configurés, va sur ton instance Langfuse et navigue dans **Traces**. Chaque appel d'outil apparaît comme une observation de type `tool`.

### Langfuse self-hosted avec Docker Compose

Si tu veux faire tourner Langfuse localement, tu peux l'ajouter à ton `docker-compose.override.yml` :

```yaml
services:
  mcp-server:
    environment:
      LANGFUSE_HOST: http://langfuse:3000
    depends_on:
      - langfuse

  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:password@langfuse-db/langfuse
      NEXTAUTH_SECRET: changeme
      SALT: changeme
      NEXTAUTH_URL: http://localhost:3000

  langfuse-db:
    image: postgres:15
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: password
      POSTGRES_DB: langfuse
```

> Pour une vraie installation Langfuse, consulte [la documentation officielle](https://langfuse.com/docs/deployment/self-host).

---

## Déploiement derrière un reverse proxy (nginx / Traefik)

### Nginx

```nginx
server {
    listen 80;
    server_name mon-mcp.exemple.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Important pour les réponses SSE (Server-Sent Events)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

### Traefik (labels Docker)

```yaml
# docker-compose.yml
services:
  mcp-server:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mcp.rule=Host(`mon-mcp.exemple.com`)"
      - "traefik.http.routers.mcp.tls=true"
      - "traefik.http.routers.mcp.tls.certresolver=letsencrypt"
      - "traefik.http.services.mcp.loadbalancer.server.port=8000"
```

> Les réponses MCP utilisent **Server-Sent Events (SSE)**. Assure-toi que ton proxy ne bufferise pas les réponses (`proxy_buffering off` pour nginx).

---

## Variables d'environnement en production

Ne mets jamais les secrets directement dans `docker-compose.yml`. Utilise :

**Option 1 : fichier `.env`** (simple, adapté aux petits projets)
```bash
# .env non commité
API_KEYS=["sk-prod-abc123"]
LANGFUSE_SECRET_KEY=sk-lf-...
```

**Option 2 : Docker Secrets** (recommandé pour les environnements orchestrés)
```yaml
services:
  mcp-server:
    secrets:
      - api_keys
    environment:
      API_KEYS_FILE: /run/secrets/api_keys

secrets:
  api_keys:
    file: ./secrets/api_keys.txt
```

**Option 3 : Variables injectées par CI/CD** (GitHub Actions, GitLab CI...)
```yaml
# .github/workflows/deploy.yml
- name: Deploy
  env:
    API_KEYS: ${{ secrets.MCP_API_KEYS }}
    LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
  run: docker compose up -d
```

---

## Checklist de mise en production

- [ ] `AUTH_MODE` est `api_key` ou `oauth2` (jamais `none`)
- [ ] `API_KEYS` contient des clés longues et aléatoires
- [ ] Le fichier `.env` n'est pas commité dans git
- [ ] `LOG_LEVEL` est `info` ou `warning` (pas `debug`)
- [ ] Le healthcheck Docker fonctionne (`docker compose ps`)
- [ ] Le serveur est accessible depuis Open WebUI
- [ ] `restart: unless-stopped` est configuré dans `docker-compose.yml`
- [ ] Un reverse proxy gère HTTPS si exposé sur internet
