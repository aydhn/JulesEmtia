#!/bin/bash
# Phase 9: Management Script for ED Capital Quant Engine

ACTION=$1

case "$ACTION" in
    start)
        echo "Starting ED Capital Quant Engine via Docker..."
        docker-compose up -d --build
        ;;
    stop)
        echo "Stopping ED Capital Quant Engine..."
        docker-compose down
        ;;
    restart)
        echo "Restarting ED Capital Quant Engine..."
        docker-compose down
        docker-compose up -d --build
        ;;
    logs)
        echo "Tailing logs..."
        docker logs -f ed_quant_engine
        ;;
    status)
        echo "Status:"
        docker ps | grep ed_quant_engine
        ;;
    *)
        echo "Usage: ./manage_bot.sh {start|stop|restart|logs|status}"
        ;;
esac
