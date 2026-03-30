#!/bin/bash
# ED Capital Quant Engine Management Script

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

case "$1" in
    start)
        echo "Starting ED Quant Engine via Docker Compose..."
        docker-compose up -d --build
        ;;
    stop)
        echo "Stopping ED Quant Engine..."
        docker-compose down
        ;;
    logs)
        docker-compose logs -f
        ;;
    status)
        docker-compose ps
        ;;
    restart)
        $0 stop
        $0 start
        ;;
    *)
        echo "Usage: \$0 {start|stop|restart|logs|status}"
        exit_code=1
        ;;
esac\n