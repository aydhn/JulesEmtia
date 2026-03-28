#!/bin/bash
# Phase 9: Systemd & Session Management
SERVICE_NAME="quant_bot"

case "$1" in
    start)
        sudo systemctl start $SERVICE_NAME
        echo "🟢 ED Capital Quant Engine Başlatıldı."
        ;;
    stop)
        sudo systemctl stop $SERVICE_NAME
        echo "🔴 ED Capital Quant Engine Durduruldu."
        ;;
    restart)
        sudo systemctl restart $SERVICE_NAME
        echo "🔄 ED Capital Quant Engine Yeniden Başlatıldı."
        ;;
    status)
        sudo systemctl status $SERVICE_NAME
        ;;
    logs)
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    tmux-fallback)
        echo "Systemd yoksa B-Planı: Tmux ile başlatılıyor..."
        tmux new-session -d -s ed_quant 'python3 main.py'
        echo "Tmux session başlatıldı. Bağlanmak için: tmux attach -t ed_quant"
        ;;
    *)
        echo "Kullanım: \$0 {start|stop|restart|status|logs|tmux-fallback}"
        ;;
esac
