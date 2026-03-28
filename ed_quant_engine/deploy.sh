#!/bin/bash
# Phase 25: One-click Docker Deployment

echo "🚀 Starting ED Capital Quant Engine Deployment..."

# Ensure persistent directories exist locally
mkdir -p logs models reports

echo "1. Shutting down old containers (if any)..."
docker-compose down

echo "2. Building new Docker image (Python Slim)..."
docker-compose build --no-cache

echo "3. Starting ED Quant Engine in detached mode..."
docker-compose up -d

echo "4. Checking container status..."
docker ps | grep ed_quant_engine

echo "✅ Deployment Complete! Bot is now running 7/24."
echo "Use 'docker logs -f ed_quant_engine_prod' to monitor."
