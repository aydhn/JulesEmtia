#!/bin/bash
# ED Capital Quant Engine Management Script
COMMAND=$1

case $COMMAND in
  start)
    echo "Starting ED Capital Quant Engine..."
    mkdir -p data logs
    chmod 777 data logs
    docker-compose up -d --build
    ;;
  stop)
    echo "Stopping ED Capital Quant Engine..."
    docker-compose down
    ;;
  restart)
    echo "Restarting ED Capital Quant Engine..."
    docker-compose down
    mkdir -p data logs
    chmod 777 data logs
    docker-compose up -d --build
    ;;
  logs)
    docker-compose logs -f
    ;;
  status)
    docker-compose ps
    ;;
  *)
    echo "Usage: ./manage_bot.sh {start|stop|restart|logs|status}"
    ;;
esac
