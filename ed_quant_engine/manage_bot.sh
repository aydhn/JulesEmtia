#!/bin/bash
chmod +x "$0"
case "$1" in
    start)
        touch paper_db.sqlite3 rf_model.pkl
        mkdir -p logs
        docker-compose up -d --build
        ;;
    stop)
        docker-compose down
        ;;
    logs)
        docker-compose logs -f --tail=100
        ;;
    status)
        docker-compose ps
        ;;
    *)
        echo "Kullanım: $0 {start|stop|logs|status}"
        ;;
esac
