#!/bin/bash

# Phase 9: Management Script for OS Integration
cd "$(dirname "$0")"

if [ "$1" == "start" ]; then
    echo "Starting ED Capital Quant Engine..."
    docker-compose up -d --build
elif [ "$1" == "stop" ]; then
    echo "Stopping Engine..."
    docker-compose down
elif [ "$1" == "logs" ]; then
    docker-compose logs -f --tail 100
elif [ "$1" == "restart" ]; then
    echo "Restarting Engine..."
    docker-compose down
    docker-compose up -d --build
else
    echo "Usage: ./manage_bot.sh {start|stop|restart|logs}"
fi
