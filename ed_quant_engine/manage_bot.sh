#!/bin/bash
case "$1" in
    start)
        echo "🚀 ED Capital Quant Engine başlatılıyor..."
        docker-compose up -d --build
        ;;
    stop)
        echo "⏸ Sistem durduruluyor..."
        docker-compose down
        ;;
    logs)
        docker-compose logs -f --tail=100
        ;;
    status)
        docker ps | grep edcapital_quant
        ;;
    *)
        echo "Kullanım: ./manage_bot.sh {start|stop|logs|status}"
        ;;
esac
