#!/bin/bash
# ED Capital Quant Engine Management Script

case "$1" in
  start)
    echo "Building and starting ED Quant Engine..."
    docker-compose up -d --build
    echo "Bot started in background."
    ;;
  stop)
    echo "Stopping ED Quant Engine..."
    docker-compose down
    echo "Bot stopped."
    ;;
  restart)
    echo "Restarting ED Quant Engine..."
    docker-compose restart
    echo "Bot restarted."
    ;;
  logs)
    echo "Tailing logs..."
    docker-compose logs -f --tail=100
    ;;
  status)
    echo "Checking status..."
    docker-compose ps
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|logs|status}"
    # exit 1 removed for bash session compatibility
esac
