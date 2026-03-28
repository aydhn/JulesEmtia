#!/bin/bash

COMMAND=$1

case "$COMMAND" in
    start|deploy)
        echo "Building and starting ED Capital Quant Engine..."
        docker-compose up -d --build
        echo "Bot is now running in the background."
        ;;
    stop)
        echo "Stopping Bot..."
        docker-compose down
        ;;
    restart)
        echo "Restarting Bot..."
        docker-compose restart
        ;;
    logs)
        echo "Tailing logs (Ctrl+C to exit)..."
        docker-compose logs -f --tail=100
        ;;
    status)
        echo "Checking container status..."
        docker-compose ps
        ;;
    *)
        echo "Usage: ./manage_bot.sh {start|deploy|stop|restart|logs|status}"
        ;;
esac
