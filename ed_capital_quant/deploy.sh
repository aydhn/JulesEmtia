#!/bin/bash
echo "🚀 ED Capital Quant Engine Dağıtımı Başlatılıyor..."

# .env Kontrolü
if [ ! -f .env ]; then
    echo "HATA: .env dosyası bulunamadı! Lütfen .env.template dosyasını kopyalayıp düzenleyin."
    return 1
fi

echo "📦 Eski Docker Konteynerleri Temizleniyor..."
docker-compose down

echo "🏗️ Yeni İmaj Derleniyor (Build)..."
docker-compose build --no-cache

echo "🟢 Servis Arka Planda Başlatılıyor (Detached)..."
docker-compose up -d

echo "✅ Dağıtım Başarılı!"
echo "Logları izlemek için: docker logs -f ed_capital_quant_bot"
