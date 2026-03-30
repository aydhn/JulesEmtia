#!/bin/bash

# Renkler
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SERVICE_NAME="quant_bot.service"

show_help() {
  echo "ED Capital Quant Engine Yönetim Betiği"
  echo "Kullanım: ./manage_bot.sh [start|stop|restart|status|logs|docker-deploy]"
}

case "$1" in
  start)
    echo -e "${GREEN}ED Quant Engine başlatılıyor...${NC}"
    sudo systemctl start $SERVICE_NAME
    sudo systemctl status $SERVICE_NAME --no-pager
    ;;
  stop)
    echo -e "${RED}ED Quant Engine durduruluyor...${NC}"
    sudo systemctl stop $SERVICE_NAME
    ;;
  restart)
    echo -e "${GREEN}ED Quant Engine yeniden başlatılıyor...${NC}"
    sudo systemctl restart $SERVICE_NAME
    ;;
  status)
    sudo systemctl status $SERVICE_NAME
    ;;
  logs)
    journalctl -u $SERVICE_NAME -f
    ;;
  docker-deploy)
    echo -e "${GREEN}Eski imajlar temizleniyor ve Docker baştan derleniyor...${NC}"
    docker-compose down
    docker-compose up -d --build
    echo -e "${GREEN}Docker ayağa kaldırıldı. Logları izlemek için: docker-compose logs -f${NC}"
    ;;
  *)
    show_help
    ;;
esac
