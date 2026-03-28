#!/bin/bash
# Phase 9: Management Script for Local (Tmux/Systemd fallback)

ACTION=$1

case $ACTION in
  start)
    echo "Starting ED Quant Engine in background (Tmux)..."
    tmux new-session -d -s quant_bot "source venv/bin/activate && python main.py"
    echo "Started. Use 'tmux attach -t quant_bot' to view."
    ;;
  stop)
    echo "Stopping ED Quant Engine..."
    tmux kill-session -t quant_bot
    echo "Stopped."
    ;;
  logs)
    cat logs/quant_engine.log | tail -n 50
    ;;
  status)
    tmux ls | grep quant_bot
    ;;
  *)
    echo "Usage: ./manage_bot.sh {start|stop|logs|status}"
    ;;
esac
