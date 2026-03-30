#!/bin/bash

# management script for docker or systemd

ACTION=$1

case "$ACTION" in
    start)
        echo "Starting ED Quant Engine via Docker Compose..."
        docker-compose up -d --build
        ;;
    stop)
        echo "Stopping ED Quant Engine..."
        docker-compose down
        ;;
    restart)
        echo "Restarting ED Quant Engine..."
        docker-compose down
        docker-compose up -d --build
        ;;
    logs)
        echo "Tailing logs..."
        docker-compose logs -f
        ;;
    status)
        echo "Checking status..."
        docker-compose ps
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status}"
        return 1
        ;;
esac
