# Apache-2.0
# Copyright (C) Cloud-Dog, Viewdeck Engineering Ltd.
#
# Place runtime CA and TLS certificates in this folder when running with Docker.
#
# Expected container paths:
# - /app/certs/ca.crt       (optional CA bundle for outbound TLS trust)
# - /app/certs/server.crt   (optional MCP TLS certificate)
# - /app/certs/server.key   (optional MCP TLS private key)
#
# Recommended run flags:
# -v $(pwd)/certs:/app/certs:ro
#
# Optional environment variables (example):
# SSL_CERT_FILE=/app/certs/ca.crt
# REQUESTS_CA_BUNDLE=/app/certs/ca.crt
