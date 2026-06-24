# Créer des outils (tools)

C'est le cœur du développement avec ce template. Cette page t'explique tout ce dont tu as besoin pour créer des outils MCP, des plus simples aux plus avancés.

---

## Anatomie d'un outil

Voici l'outil `ping` existant, décortiqué ligne par ligne :

```python
# src/mcp_server/tools/system/ping.py

from mcp_server.observability.langfuse import trace_tool   # (1) Traçabilité
from mcp_server.server import mcp                          # (2) L'instance FastMCP partagée
from mcp_server.utils.datetime import iso_now              # (3) Utilitaire partagé


@mcp.tool(description="Returns pong. Use this to test connectivity.")  # (4) Déclaration
async def ping() -> dict[str, str]:                                    # (5) Signature
    """Returns pong with a UTC timestamp."""                            # (6) Docstring
    async with trace_tool("ping"):                                      # (7) Trace Langfuse
        return {"message": "pong", "timestamp": iso_now()}             # (8) Résultat
```

| # | Ce que c'est | Pourquoi |
|---|---|---|
| 1 | Import du context manager de traçabilité | Pour enregistrer chaque appel dans Langfuse |
| 2 | Import de l'instance `mcp` depuis `server.py` | **Toujours importer depuis là** — c'est l'objet FastMCP partagé |
| 3 | Import d'une fonction utilitaire | Réutiliser du code partagé plutôt que de le dupliquer |
| 4 | Décorateur `@mcp.tool()` | Enregistre la fonction comme outil MCP avec sa description |
| 5 | Signature `async def` avec types | Tous les outils sont **async** et **typés** |
| 6 | Docstring | Documentation interne du code |
| 7 | `async with trace_tool(...)` | Wrapping de l'exécution pour Langfuse (no-op si désactivé) |
| 8 | `return dict` | La valeur retournée est envoyée au LLM |

> **Règle d'or** : La `description` du `@mcp.tool()` est ce que le LLM lit pour décider d'utiliser l'outil. Rédige-la en anglais, de manière claire et orientée action. C'est le texte le plus important de ton outil.

---

## Cas 1 : Ajouter un outil à une famille existante

C'est le cas le plus courant. Exemple : ajouter un outil `word_counter` à la famille `text`.

### Étape 1 — Créer le fichier de l'outil

```
src/mcp_server/tools/text/word_counter.py   ← nouveau fichier
```

```python
# src/mcp_server/tools/text/word_counter.py

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.text import word_count


@mcp.tool(description="Count the number of words in a given text.")
async def count_words(text: str) -> dict:
    """Returns the word count for the provided text."""
    async with trace_tool("count_words", inputs={"text_length": len(text)}):
        return {"word_count": word_count(text)}
```

### Étape 2 — Déclarer l'outil dans l'`__init__.py` de la famille

```python
# src/mcp_server/tools/text/__init__.py

from . import summary
from . import word_counter   # ← ajouter cette ligne
```

**C'est tout.** Le serveur découvrira l'outil automatiquement au prochain démarrage.

---

## Cas 2 : Créer une nouvelle famille d'outils

Exemple : créer une famille `weather` pour des outils liés à la météo.

### Étape 1 — Créer le dossier et son `__init__.py`

```
src/mcp_server/tools/weather/
├── __init__.py
└── current_weather.py
```

```python
# src/mcp_server/tools/weather/__init__.py

from . import current_weather
```

### Étape 2 — Créer l'outil

```python
# src/mcp_server/tools/weather/current_weather.py

import httpx

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp


@mcp.tool(description="Get the current weather for a given city.")
async def get_current_weather(city: str) -> dict:
    """Fetches current weather data for the specified city."""
    async with trace_tool("get_current_weather", inputs={"city": city}):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://wttr.in/{city}?format=j1".format(city=city)
            )
            data = response.json()
            current = data["current_condition"][0]
            return {
                "city": city,
                "temperature_c": int(current["temp_C"]),
                "description": current["weatherDesc"][0]["value"],
                "humidity": int(current["humidity"]),
            }
```

> L'auto-découverte dans `src/mcp_server/tools/__init__.py` scan tous les sous-dossiers avec `pkgutil.iter_modules`. **Tu n'as rien à modifier dans ce fichier.** Créer le dossier `weather/` avec un `__init__.py` suffit.

---

## Définir les paramètres d'un outil

FastMCP convertit automatiquement la signature Python en schéma JSON que le LLM utilise. Voici comment définir des paramètres complexes :

### Paramètres simples

```python
@mcp.tool(description="Add two numbers.")
async def add(a: float, b: float) -> dict:
    return {"result": a + b}
```

### Paramètres optionnels avec valeur par défaut

```python
@mcp.tool(description="Greet someone with an optional custom message.")
async def greet(name: str, message: str = "Hello") -> dict:
    return {"greeting": f"{message}, {name}!"}
```

### Paramètre avec description enrichie (Annotated)

```python
from typing import Annotated
from pydantic import Field

@mcp.tool(description="Search for documents matching a query.")
async def search_documents(
    query: Annotated[str, Field(description="The search query in natural language")],
    max_results: Annotated[int, Field(description="Maximum number of results to return", ge=1, le=50)] = 10,
) -> dict:
    # ...
    return {"results": [], "total": 0}
```

> Utiliser `Annotated` + `Field` permet de fournir au LLM des descriptions détaillées pour chaque paramètre, ce qui améliore la précision des appels.

### Paramètre énuméré (choix limités)

```python
from typing import Literal

@mcp.tool(description="Convert text to a specific case format.")
async def convert_case(
    text: str,
    format: Literal["upper", "lower", "title", "snake_case"],
) -> dict:
    if format == "upper":
        return {"result": text.upper()}
    elif format == "lower":
        return {"result": text.lower()}
    elif format == "title":
        return {"result": text.title()}
    else:
        return {"result": text.replace(" ", "_").lower()}
```

---

## Utiliser les utilitaires partagés

Le dossier `utils/` contient des fonctions pures réutilisables. Elles ne dépendent d'aucun framework.

### `utils/text.py`

```python
from mcp_server.utils.text import truncate, word_count, sanitize

# Tronquer un texte à 100 caractères (avec "..." à la fin si tronqué)
short = truncate("Un texte très long...", max_length=100)
short = truncate("Un texte très long...", max_length=100, suffix=" [lire la suite]")

# Compter les mots
n = word_count("Bonjour tout le monde")  # → 4

# Nettoyer les espaces et sauts de ligne multiples
clean = sanitize("  Du texte\n\n\n\navec des espaces  ")
```

### `utils/datetime.py`

```python
import time
from mcp_server.utils.datetime import iso_now, elapsed_ms

# Obtenir la date/heure UTC en format ISO 8601
ts = iso_now()  # → "2026-06-24T10:30:00.123456+00:00"

# Mesurer la durée d'exécution
start = time.perf_counter()
# ... ton code ...
duration = elapsed_ms(start)  # → 42 (ms)
```

### Créer un nouvel utilitaire

Si tu as besoin d'une fonction réutilisable dans plusieurs outils, crée-la dans `utils/` :

```python
# src/mcp_server/utils/formatting.py

def format_bytes(size: int) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
```

**Règles pour les utilitaires** :
- Fonctions pures uniquement (entrée → sortie, sans effets de bord)
- Pas d'imports de `config`, `server`, ou de code MCP/FastAPI
- Pas de logging, pas d'I/O
- Si un fichier dépasse ~10 fonctions, le découper en fichiers plus ciblés

---

## Ajouter la traçabilité Langfuse

Chaque outil doit wrapper son exécution dans `trace_tool`. C'est un no-op si Langfuse est désactivé.

### Usage minimal

```python
from mcp_server.observability.langfuse import trace_tool

@mcp.tool(description="...")
async def mon_outil(texte: str) -> dict:
    async with trace_tool("mon_outil"):
        return {"resultat": texte.upper()}
```

### Avec les inputs enregistrés

Passer les inputs à `trace_tool` permet de les voir dans Langfuse (sans enregistrer de données sensibles) :

```python
async with trace_tool("mon_outil", inputs={"longueur": len(texte), "type": "analyse"}):
    # ...
```

> Ne passe jamais de données sensibles (mots de passe, tokens, PII) dans `inputs`.

---

## Exemple complet : outil de recherche d'emails

Voici un exemple réaliste qui montre toutes les bonnes pratiques :

```python
# src/mcp_server/tools/email/search.py

import re
from typing import Annotated

from pydantic import Field

from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.text import sanitize


def _extract_emails(text: str) -> list[str]:
    """Extract all email addresses found in text."""
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    return list(set(re.findall(pattern, text)))


@mcp.tool(
    description=(
        "Extract all email addresses found in a text. "
        "Returns a deduplicated list of valid email addresses."
    )
)
async def extract_emails(
    text: Annotated[str, Field(description="The text to search for email addresses")],
) -> dict:
    """Finds and returns all unique email addresses in the provided text."""
    async with trace_tool("extract_emails", inputs={"text_length": len(text)}):
        cleaned = sanitize(text)
        emails = _extract_emails(cleaned)
        return {
            "emails": emails,
            "count": len(emails),
        }
```

Pour enregistrer cet outil :
```python
# src/mcp_server/tools/email/__init__.py
from . import search
```

---

## Checklist avant de déployer un outil

- [ ] La `description` est rédigée en anglais, claire, orientée action
- [ ] Tous les paramètres sont typés
- [ ] La fonction est `async`
- [ ] `async with trace_tool(...)` entoure le code métier
- [ ] L'outil est importé dans le `__init__.py` de sa famille
- [ ] Un test couvre le cas nominal (optionnel mais recommandé)
- [ ] Pas de secrets hardcodés dans le code — utiliser `config.py`
