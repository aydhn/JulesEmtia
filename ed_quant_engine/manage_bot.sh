#!/bin/bash

# ED Capital Quant Engine Management Script

set -e

# Project paths
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COMPOSE_FILE="$DIR/docker-compose.yml"

print_help() {
    echo "ED Capital Quant Engine Management"
    echo "Usage: ./manage_bot.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start     Start the bot in the background (Docker)"
    echo "  stop      Stop the bot"
    echo "  restart   Restart the bot"
    echo "  logs      Follow the bot logs"
    echo "  status    Show container status"
    echo "  build     Rebuild the Docker image"
    echo "  update    Rebuild and restart"
}

case "$1" in
    start)
        echo "Starting ED Capital Quant Engine..."
        docker-compose -f "$COMPOSE_FILE" up -d
        echo "Bot started successfully."
        ;;
    stop)
        echo "Stopping ED Capital Quant Engine..."
        docker-compose -f "$COMPOSE_FILE" down
        echo "Bot stopped."
        ;;
    restart)
        echo "Restarting ED Capital Quant Engine..."
        docker-compose -f "$COMPOSE_FILE" restart
        echo "Bot restarted."
        ;;
    logs)
        docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
        ;;
    status)
        docker-compose -f "$COMPOSE_FILE" ps
        ;;
    build)
        echo "Building Docker image..."
        docker-compose -f "$COMPOSE_FILE" build
        ;;
    update)
        echo "Updating bot..."
        docker-compose -f "$COMPOSE_FILE" build
        docker-compose -f "$COMPOSE_FILE" down
        docker-compose -f "$COMPOSE_FILE" up -d
        echo "Update completed."
        ;;
    *)
        print_help
        ;;
esac
