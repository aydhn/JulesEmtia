#!/bin/bash
# High-Availability Deployment Script

echo "🚀 Starting ED Capital Quant Engine Deployment..."

# Ensure .env exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file is missing! Create it before deploying."
    echo "Format: TELEGRAM_BOT_TOKEN=... ADMIN_CHAT_ID=..."
else
    # Set permissions for the volumes on host to match container user
    mkdir -p logs models reports
    touch paper_db.sqlite3

    # Build and start container (detached mode)
    echo "🐳 Building Docker image..."
    docker-compose up -d --build

    echo "✅ Deployment successful!"
    echo "📄 To view live logs: docker logs -f ed_quant_engine"
fi
