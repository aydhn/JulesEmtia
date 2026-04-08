#!/bin/bash

case "$1" in
    start)
        echo "Starting ED Capital Quant Engine..."
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
        docker-compose logs -f
        ;;
    status)
        docker-compose ps
        ;;
    *)
        echo "Usage: \$0 {start|stop|restart|logs|status}"
        ;;
esac
