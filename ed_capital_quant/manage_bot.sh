#!/bin/bash
case "$1" in
    start)
        sudo systemctl start quant_bot
        echo "Başlatıldı."
        ;;
    stop)
        sudo systemctl stop quant_bot
        echo "Durduruldu."
        ;;
    restart)
        sudo systemctl restart quant_bot
        echo "Yeniden başlatıldı."
        ;;
    status)
        sudo systemctl status quant_bot
        ;;
    logs)
        journalctl -u quant_bot -f
        ;;
    *)
        echo "Kullanım: $0 {start|stop|restart|status|logs}"
        ;;
esac
