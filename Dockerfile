FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Africa/Dar_es_Salaam
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tzdata sqlite3 curl \
    && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 1000 mvf
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
RUN mkdir -p /app/data /app/backups && chown -R mvf:mvf /app
USER mvf
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8000/health || exit 1
# One worker: the background scheduler runs inside the app process and SQLite prefers a single writer.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
