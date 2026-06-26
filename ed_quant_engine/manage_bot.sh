#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

case "${1:-}" in
    start)
        echo "Starting JulesEmtia Quant Engine..."
        compose up -d --build
        ;;
    stop)
        echo "Stopping JulesEmtia Quant Engine..."
        compose down
        ;;
    restart)
        echo "Restarting JulesEmtia Quant Engine..."
        compose down
        compose up -d --build
        ;;
    logs)
        compose logs -f --tail=200
        ;;
    status)
        compose ps
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status}"
        exit 2
        ;;
esac
