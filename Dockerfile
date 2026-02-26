FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (layer caching)
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psycopg2-binary uvicorn[standard]

# Copy application source
COPY asclepius/ ./asclepius/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Install the package itself
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "asclepius.api:app", "--host", "0.0.0.0", "--port", "8000"]
