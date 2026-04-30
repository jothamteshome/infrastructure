#!/bin/bash
set -e

source /etc/profile.d/init-env.sh

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
BUCKET="app-backups-108782084399-us-east-1-an"

docker exec postgres pg_dump -U "$POSTGRES_USER" whymighta_db \
    | gzip \
    | aws s3 cp - "s3://$BUCKET/perpetual-app-host/postgres-backups/whymighta_$TIMESTAMP.sql.gz" --region us-east-1

echo "Backup completed: whymighta_$TIMESTAMP.sql.gz"