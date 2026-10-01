# ============================================================================
# AvtomaktabPlatforma — production image
# YADRO (server, DB, API, bot) faqat Python STDLIB ishlatadi.
# Qo'shimcha: `openpyxl` + `reportlab` — FAQAT hisobot eksporti (XLSX/PDF).
# Ularsiz ham platforma ishlaydi: CSV har doim, XLSX/PDF 503 qaytaradi.
# ============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# Kodni nusxalash (fayl sathi: .dockerignore orqali filtrlash mumkin)
COPY requirements.txt ./
COPY server.py ./
COPY app/ ./app/
COPY web/ ./web/
COPY scripts/ ./scripts/

# --- PDF shrifti ---
# O'zbekcha SHEVA belgilari (oʻ, gʻ, ǒ, ǔ) Base14 shriftlarda YO'Q — PDF'da
# kvadratchalar chiqardi. DejaVu shrifti ularni to'liq qo'llab-quvvatlaydi.
# `fonts-dejavu-core` ~700 kB (to'liq dejavu paketidan kichik).
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# --- hisobot eksporti (XLSX/PDF) ---
RUN pip install --no-cache-dir -r requirements.txt

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