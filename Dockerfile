# ============================================================================
# AvtomaktabPlatforma — production image
# Ilova faqat Python STDLIB ishlatadi (http.server + sqlite3) —
# pip install / requirements.txt SHART EMAS.
# ============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# Kodni nusxalash (fayl sathi: .dockerignore orqali filtrlash mumkin)
COPY server.py ./
COPY app/ ./app/
COPY web/ ./web/
COPY scripts/ ./scripts/

# Root sifatida ishlamaymiz — xavfsizlik uchun oddiy foydalanuvchi
RUN addgroup --system avtomaktab \
    && adduser --system --ingroup avtomaktab --home /app avtomaktab \
    && mkdir -p /app/data/backups \
    && chown -R avtomaktab:avtomaktab /app

USER avtomaktab

# SQLite baza shu yerga yoziladi — docker volume bilan saqlanadi
VOLUME ["/app/data"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
r=urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3); \
sys.exit(0 if r.status==200 else 1)"

CMD ["python", "server.py"]