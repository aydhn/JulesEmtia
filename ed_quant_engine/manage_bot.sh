#!/bin/bash

# ED Capital Quant Engine - Yönetim ve Dağıtım Betiği

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Ensure log and models directories exist before starting Docker
mkdir -p logs models reports
touch paper_db.sqlite3 # Create empty DB file if it doesn't exist for Volume mapping

case "$1" in
    start)
        echo "🚀 ED Capital Quant Engine başlatılıyor (Detached Mod)..."
        docker-compose up -d --build
        ;;
    stop)
        echo "⏹️ ED Capital Quant Engine durduruluyor..."
        docker-compose down
        ;;
    restart)
        echo "🔄 ED Capital Quant Engine yeniden başlatılıyor..."
        docker-compose down
        docker-compose up -d --build
        ;;
    logs)
        echo "📜 Loglar takip ediliyor (Çıkmak için Ctrl+C)..."
        docker-compose logs -f --tail=100
        ;;
    status)
        echo "ℹ️ ED Capital Quant Engine Konteyner Durumu:"
        docker ps | grep ed_quant_engine
        ;;
    *)
        echo "Kullanım: $0 {start|stop|restart|logs|status}"
        # removed exit 1 to not block bash session
        ;;
esac
