#!/bin/bash
# Phase 9 & 25: Management Script

COMMAND=$1

case "$COMMAND" in
    start)
        echo "Starting ED Capital Quant Engine via Docker Compose..."
        docker-compose up -d --build
        ;;
    stop)
        echo "Stopping Engine..."
        docker-compose down
        ;;
    logs)
        docker-compose logs -f --tail=100
        ;;
    restart)
        echo "Restarting Engine..."
        docker-compose down
        docker-compose up -d --build
        ;;
    status)
        docker-compose ps
        ;;
    *)
        echo "Usage: ./manage_bot.sh {start|stop|restart|logs|status}"
esac
