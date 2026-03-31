#!/bin/bash

function show_help {
    echo "Usage: ./manage_bot.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start       Starts the ED Quant Engine using docker-compose."
    echo "  stop        Stops the engine."
    echo "  restart     Restarts the engine."
    echo "  logs        Tails the container logs."
    echo "  status      Shows the status of the container."
    echo "  deploy      Rebuilds the image and starts the container."
    echo ""
}

case $1 in
    start)
        echo "Starting ED Quant Engine..."
        docker-compose up -d
        ;;
    stop)
        echo "Stopping ED Quant Engine..."
        docker-compose down
        ;;
    restart)
        echo "Restarting ED Quant Engine..."
        docker-compose restart
        ;;
    logs)
        echo "Tailing logs for ED Quant Engine (Press Ctrl+C to exit)..."
        docker-compose logs -f
        ;;
    status)
        echo "Checking status of ED Quant Engine..."
        docker-compose ps
        ;;
    deploy)
        echo "Deploying ED Quant Engine..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        ;;
    *)
        show_help
        ;;
esac
