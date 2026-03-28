#!/bin/bash

# manage_bot.sh - ED Capital Quant Engine Management Script

set -e

action=$1

case $action in
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
    docker-compose logs -f quant_engine
    ;;
  status)
    docker-compose ps
    ;;
  shell)
    docker-compose exec quant_engine /bin/bash
    ;;
  *)
    echo "Usage: ./manage_bot.sh {start|stop|restart|logs|status|shell}"
    ;;
esac
