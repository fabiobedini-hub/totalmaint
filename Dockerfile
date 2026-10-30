# Debian 13 "trixie": its pg_dump (PostgreSQL 17) can back up the PostgreSQL 16 database,
# which TotalMant Admin's "Backup now" needs.
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY frontend frontend
COPY admin admin

WORKDIR /app/backend
EXPOSE 8000 8001
# TotalMaint itself; the admin console uses the same image with another command (docker-compose.yml)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
