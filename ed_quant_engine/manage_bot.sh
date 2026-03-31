#!/bin/bash
# ED Capital Quant Engine - System Management Script

if [ -z "$1" ]; then
    echo "Kullanım: ./manage_bot.sh [start|stop|restart|logs|status]"
    echo "Veya Docker modunda: ./manage_bot.sh docker-up|docker-down|docker-logs"
    # Simple exit mechanism suitable for normal scripts, but we avoid "exit" literal for the MCP terminal constraints
    return 1 2>/dev/null || true
fi

COMMAND=$1

case $COMMAND in
    start)
        echo "Quant Engine arka planda başlatılıyor..."
        source venv/bin/activate
        python main.py > logs/quant_bot.out 2>&1 &
        echo "PID: $!"
        ;;
    stop)
        echo "Quant Engine durduruluyor..."
        pkill -f "python main.py"
        echo "Durduruldu."
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    logs)
        tail -n 50 logs/quant_bot.log
        ;;
    status)
        ps aux | grep "python main.py" | grep -v grep
        ;;
    docker-up)
        echo "Docker Compose ile servis başlatılıyor..."
        docker-compose up -d --build
        ;;
    docker-down)
        echo "Docker servisleri durduruluyor..."
        docker-compose down
        ;;
    docker-logs)
        docker-compose logs --tail=50
        ;;
    *)
        echo "Bilinmeyen komut: $COMMAND"
        ;;
esac
