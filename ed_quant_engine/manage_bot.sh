#!/bin/bash
# ED Capital Quant Engine Management Script

case "$1" in
  start)
    echo "Starting ED Quant Engine in detached mode..."
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
    echo "Tailing logs (press Ctrl+C to exit)..."
    docker-compose logs -f --tail=100
    ;;
  status)
    docker-compose ps
    ;;
  *)
    echo "Usage: manage_bot.sh {start|stop|restart|logs|status}"
    ;;
esac
