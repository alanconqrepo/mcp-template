FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN touch README.md

RUN uv pip install --system --no-dev .

COPY src/ ./src/

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "mcp_server.app:app", "--host", "0.0.0.0", "--port", "8000"]
