#!/bin/bash
case "$1" in
  start)
    docker-compose up -d --build
    ;;
  stop)
    docker-compose down
    ;;
  logs)
    docker-compose logs -f --tail=100
    ;;
  *)
    echo "Kullanım: ./manage_bot.sh {start|stop|logs}"
    # No exit 1 here to avoid terminating bash session
esac
