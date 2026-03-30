#!/bin/bash

# A unified bash script to manage the ED Capital Quant Engine via Docker Compose.

ACTION=$1

case "$ACTION" in
    start)
        echo "Starting ED Quant Engine in background..."
        docker-compose up -d --build
        ;;
    stop)
        echo "Stopping ED Quant Engine..."
        docker-compose down
        ;;
    restart)
        echo "Restarting ED Quant Engine..."
        docker-compose restart
        ;;
    logs)
        echo "Tailing logs... (Press Ctrl+C to exit)"
        docker-compose logs -f --tail=100
        ;;
    status)
        echo "Checking container status..."
        docker-compose ps
        ;;
    *)
        echo "Usage: ./manage_bot.sh {start|stop|restart|logs|status}"
        # Exit removed to prevent blocking bash session
        ;;
esac
