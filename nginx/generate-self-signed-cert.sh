#!/bin/bash
# Run this once before starting docker-compose.prod.yml:
#   bash nginx/generate-self-signed-cert.sh
#
# For production replace with real certs from Let's Encrypt:
#   certbot certonly --standalone -d yourdomain.com
#   cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/certs/cert.pem
#   cp /etc/letsencrypt/live/yourdomain.com/privkey.pem   nginx/certs/key.pem

set -e

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/key.pem" \
  -out    "$CERT_DIR/cert.pem" \
  -subj   "/C=IN/ST=Delhi/L=Delhi/O=MedAxis/CN=localhost"

echo "Self-signed certificate generated in $CERT_DIR"
