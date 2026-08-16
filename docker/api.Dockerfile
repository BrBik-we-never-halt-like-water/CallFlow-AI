# The API, for local development only.
#
# Dependencies are installed from pyproject at build time; the source itself is
# bind-mounted by compose, so `uvicorn --reload` picks up an edit on the host
# without a rebuild. Rebuild only when a dependency changes.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# psycopg needs libpq; alembic's migrations run through it. `--no-install-recommends`
# keeps this to what is actually linked against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/apps/api

# Copy only the manifest first, so a source edit does not invalidate the
# dependency layer.
COPY apps/api/pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY apps/api ./

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
