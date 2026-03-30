#!/bin/bash
# Phase 9 & 25: Management Script
# Usage: ./manage_bot.sh [start|stop|restart|logs|status]

COMMAND=$1

case "$COMMAND" in
    start)
        echo "Starting ED Capital Quant Engine..."
        docker-compose up -d --build
        echo "Bot started in background."
        ;;
    stop)
        echo "Stopping ED Capital Quant Engine..."
        docker-compose down
        echo "Bot stopped safely."
        ;;
    restart)
        echo "Restarting ED Capital Quant Engine..."
        docker-compose down
        docker-compose up -d --build
        echo "Bot restarted successfully."
        ;;
    logs)
        echo "Streaming logs... (Ctrl+C to exit)"
        docker-compose logs -f
        ;;
    status)
        echo "Checking container status..."
        docker-compose ps
        ;;
    *)
        echo "Usage: ./manage_bot.sh {start|stop|restart|logs|status}"
        # removed exit 1 to not kill parent shell
        ;;
esac
