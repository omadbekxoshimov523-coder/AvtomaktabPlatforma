#!/usr/bin/env bash
# ============================================================================
# AvtomaktabPlatforma — kunlik avtomatik bazaviy zaxira (production)
#
# SQLite uchun xavfsiz ONLINE zaxira: VACUUM INTO (server ishlayotganda ham
# yaxlit snapshot) — scripts/db_backup.py orqali, container ichida bajariladi.
#
# Sozlash (VPS):
#   1) docker-compose.prod.yml'da ./backups host papkasi /app/data/backups'ga
#      ulanadi  -> zaxiralar hostda saqlanadi
#   2) cron'ga qo'shish (kuniga bir marta, 02:00):
#      crontab -e
#        0 2 * * * /opt/avtomaktab/scripts/backup_cron.sh >> /var/log/avtomaktab-backup.log 2>&1
#
# Bulut xotiraga yuklash (ixtiyoriy): RCLONE_REMOTE .env'da ko'rsatilsa,
# rclone bilan Backblaze B2 / S3 kabi joyga ham nusxa ko'chiriladi.
# Masalan: rclone config -> b2:avtomaktab-backups
# ============================================================================
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-/opt/avtomaktab/docker-compose.prod.yml}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# .env'ni ham o'qib olamiz (BACKUP_RETENTION_DAYS, RCLONE_REMOTE)
if [ -f "${APP_DIR}/.env" ]; then
  set -a; . "${APP_DIR}/.env"; set +a
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
RETENTION="${BACKUP_RETENTION_DAYS:-14}"

echo "[$(date +%F\ %T)] Zaxira boshlandi: db_${STAMP}.db"

# 1) Container ichida online VACUUM INTO zaxira (volume -> ./backups)
docker compose -f "${COMPOSE_FILE}" exec -T app \
  python scripts/db_backup.py --out "/app/data/backups/db_${STAMP}.db"

# 2) Host papkada saqlangan (./backups) eski nusxalarni tozalash
BACKUP_HOST_DIR="${APP_DIR}/backups"
find "${BACKUP_HOST_DIR}" -name 'db_*.db' -mtime "+${RETENTION}" -delete 2>/dev/null || true

# 3) (Ixtiyoriy) bulut xotiraga yuklash — rclone
if [ -n "${RCLONE_REMOTE:-}" ]; then
  echo "  Bulut xotiraga yuklanmoqda: ${RCLONE_REMOTE}/auto/db_${STAMP}.db"
  rclone copy "${BACKUP_HOST_DIR}/db_${STAMP}.db" "${RCLONE_REMOTE}/auto" \
    --log-file="${BACKUP_HOST_DIR}/rclone.log" || true
fi

echo "[$(date +%F\ %T)] OK: ${BACKUP_HOST_DIR}/db_${STAMP}.db"