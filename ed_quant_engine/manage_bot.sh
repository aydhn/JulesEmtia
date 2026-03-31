#!/bin/bash
# Phase 9 & 25: Management Script & Docker Deployment

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

function show_help {
    echo "Usage: ./manage_bot.sh [start|stop|restart|logs|status]"
    echo "Commands:"
    echo "  start   - Builds and starts the Docker container in detached mode."
    echo "  stop    - Stops and removes the Docker container safely."
    echo "  restart - Stops, rebuilds, and restarts the container."
    echo "  logs    - Tails the Docker logs."
    echo "  status  - Checks if the container is running."
}

case "$1" in
    start)
        echo "Starting ED Capital Quant Engine..."
        docker-compose up -d --build
        echo "Container started. Run './manage_bot.sh logs' to view output."
        ;;
    stop)
        echo "Stopping ED Capital Quant Engine..."
        docker-compose down
        echo "Container stopped safely."
        ;;
    restart)
        echo "Restarting ED Capital Quant Engine..."
        docker-compose down
        docker-compose up -d --build
        echo "Container restarted."
        ;;
    logs)
        docker-compose logs -f --tail=100
        ;;
    status)
        docker-compose ps
        ;;
    *)
        show_help
        ;;
esac
