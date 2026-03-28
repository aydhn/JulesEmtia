#!/bin/bash
set -e
echo "ED Capital Quant Engine - Docker Dağıtımı"
docker-compose down || true
docker rmi ed_quant_engine || true
docker-compose up -d --build
echo "Sistem başarıyla başlatıldı. Loglar: docker logs -f ed_quant"
