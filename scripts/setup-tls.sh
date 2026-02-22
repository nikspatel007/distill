#!/usr/bin/env bash
set -euo pipefail

DOMAIN="nik-mbp-m4max.taila28aec.ts.net"
CERT_DIR="$HOME/.config/distill/certs"

mkdir -p "$CERT_DIR"

echo "Generating TLS certs for $DOMAIN..."
tailscale cert \
  --cert-file "$CERT_DIR/$DOMAIN.crt" \
  --key-file "$CERT_DIR/$DOMAIN.key" \
  "$DOMAIN"

echo "Certs written to $CERT_DIR/"
echo ""
echo "Add to web/.env:"
echo "  TLS_CERT=$CERT_DIR/$DOMAIN.crt"
echo "  TLS_KEY=$CERT_DIR/$DOMAIN.key"
