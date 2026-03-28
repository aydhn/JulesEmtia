#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR" || exit

start() {
    echo "ED Capital Quant Engine başlatılıyor (Docker)..."
    docker-compose up -d --build
}

stop() {
    echo "ED Capital Quant Engine durduruluyor..."
    docker-compose down
}

logs() {
    echo "Loglar izleniyor... (Çıkmak için Ctrl+C)"
    docker-compose logs -f
}

status() {
    docker-compose ps
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    logs) logs ;;
    status) status ;;
    *) echo "Kullanım: $0 {start|stop|restart|logs|status}"; exit 1 ;;
esac