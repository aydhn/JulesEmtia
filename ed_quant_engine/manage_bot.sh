#!/bin/bash

# Phase 9: Start/Stop/Status/Logs Management Script
ACTION=$1

if [ -z "$ACTION" ]; then
    echo "Usage: ./manage_bot.sh [start|stop|restart|logs|status]"
else
    case $ACTION in
        start)
            echo "Starting ED Capital Quant Engine..."
            docker-compose up -d --build
            echo "Engine started in background."
            ;;
        stop)
            echo "Stopping ED Capital Quant Engine..."
            docker-compose down
            echo "Engine stopped."
            ;;
        restart)
            echo "Restarting ED Capital Quant Engine..."
            docker-compose down
            docker-compose up -d --build
            echo "Engine restarted."
            ;;
        logs)
            docker-compose logs -f
            ;;
        status)
            docker-compose ps
            ;;
        *)
            echo "Usage: ./manage_bot.sh [start|stop|restart|logs|status]"
            ;;
    esac
fi
