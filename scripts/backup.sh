#!/bin/bash
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups
RETAIN_DAYS=${BACKUP_RETAIN_DAYS:-7}

mkdir -p "$BACKUP_DIR"

DATABASES="medaxis_auth medaxis_inventory medaxis_billing medaxis_replenishment medaxis_ai medaxis_notifications"

echo "[$TIMESTAMP] Starting backup..."

for DB in $DATABASES; do
    OUT="$BACKUP_DIR/${DB}_${TIMESTAMP}.sql.gz"
    PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -U "$DB_USER" "$DB" | gzip > "$OUT"
    echo "  Backed up $DB -> $OUT"
done

find "$BACKUP_DIR" -name "*.sql.gz" -mtime "+$RETAIN_DAYS" -delete
echo "  Pruned backups older than $RETAIN_DAYS days"
echo "[$TIMESTAMP] Backup complete."
