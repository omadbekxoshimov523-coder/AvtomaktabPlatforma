# ============================================================================
# AVTOMAKTAB Telegram boti — Docker image
# Build:  docker compose -f docker-compose.prod.yml build bot
# (yoki:   docker build -f bot/Dockerfile -t avtomaktab-bot .)
# ============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY bot/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

# Root sifatida ishlamaymiz
RUN addgroup --system bot \
    && adduser --system --ingroup bot --home /app bot \
    && mkdir -p /app/data \
    && chown -R bot:bot /app

USER bot

# SQLite (bot.db) shu volume'da saqlanadi
VOLUME ["/app/data"]

CMD ["python", "-m", "bot.main"]