#!/bin/bash
set -e

INFRA_DIR="/opt/infrastructure"
COMPOSE_DIR="$INFRA_DIR/cloud/perpetual-app-host"
AWS_REGION="us-east-1"

echo "=== Installing Docker ==="
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "Docker already installed, skipping"
fi

# Allow ubuntu user to run docker without sudo
usermod -aG docker ubuntu

echo "=== Installing AWS CLI v2 ==="
if ! command -v aws &>/dev/null; then
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
    unzip -q /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install
    rm -rf /tmp/awscliv2.zip /tmp/aws
else
    echo "AWS CLI already installed, skipping"
fi

echo "=== Installing Certbot ==="
if ! command -v certbot &>/dev/null; then
    apt-get install -y certbot
else
    echo "Certbot already installed, skipping"
fi

# Set up certbot auto-renewal cron if not already present
if ! crontab -l 2>/dev/null | grep -q certbot; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && docker kill -s HUP perpetual-app-host-nginx-1") | crontab -
    echo "Certbot renewal cron added"
fi

echo "=== Fetching postgres credentials from SSM ==="
export POSTGRES_USER=$(aws ssm get-parameter \
    --name "/perpetual-app-host/db/username" \
    --with-decryption \
    --query "Parameter.Value" \
    --output text \
    --region $AWS_REGION)

export POSTGRES_PASSWORD=$(aws ssm get-parameter \
    --name "/perpetual-app-host/db/password" \
    --with-decryption \
    --query "Parameter.Value" \
    --output text \
    --region $AWS_REGION)

echo "=== Starting services ==="
cd "$COMPOSE_DIR"
docker compose pull
docker compose up -d

echo "=== Done ==="
echo "Run 'certbot certonly --nginx -d yourdomain.com' to issue SSL certificates"
