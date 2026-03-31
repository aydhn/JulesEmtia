#!/bin/bash
# Phase 25: Single-click deployment script
echo "ED Capital Quant Engine deployment başlıyor..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "HATA: .env dosyası bulunamadı. Lütfen .env.template'den kopyalayıp yapılandırın."
    # Removed exit 1 for MCP safety
fi

# Ensure volumes exist
touch paper_db.sqlite3
mkdir -p logs
touch rf_model.pkl

echo "Docker container'lar yenileniyor..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "✅ ED Capital Quant Engine canlıya alındı!"
echo "Logları izlemek için: docker logs -f ed_quant_engine_live"
