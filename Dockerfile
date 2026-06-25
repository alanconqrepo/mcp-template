FROM python:3.12-slim

# Install Microsoft ODBC Driver 18 for SQL Server
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN touch README.md

RUN uv pip install --system --no-dev .

COPY src/ ./src/

RUN python -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL azure')"

# Install Chromium for Playwright in a fixed path accessible to all users
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
RUN playwright install chromium --with-deps \
    && chmod -R a+rx /opt/pw-browsers

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "mcp_server.app:app", "--host", "0.0.0.0", "--port", "8000"]
