#!/bin/bash
# ED Capital Quant Engine Management Script

COMMAND=$1

case "$COMMAND" in
    start)
        echo "Starting bot via docker-compose..."
        docker-compose up -d
        ;;
    stop)
        echo "Stopping bot..."
        docker-compose stop
        ;;
    restart)
        echo "Restarting bot..."
        docker-compose restart
        ;;
    logs)
        echo "Showing logs..."
        docker-compose logs -f
        ;;
    status)
        docker-compose ps
        ;;
    *)
        echo "Usage: ./manage_bot.sh {start|stop|restart|logs|status}"
esac
