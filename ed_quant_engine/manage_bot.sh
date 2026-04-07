#!/bin/bash
case "$1" in
    start)
        echo "ED Capital Quant Engine başlatılıyor..."
        docker-compose up -d --build
        ;;
    stop)
        echo "Sistem durduruluyor..."
        docker-compose down
        ;;
    restart)
        echo "Sistem yeniden başlatılıyor..."
        docker-compose down
        docker-compose up -d --build
        ;;
    logs)
        echo "Loglar izleniyor..."
        docker-compose logs -f --tail=100
        ;;
    status)
        echo "Konteyner Durumu:"
        docker ps | grep ed_quant_engine
        ;;
    *)
        echo "Kullanım: ./manage_bot.sh {start|stop|restart|logs|status}"
        ;;
esac
