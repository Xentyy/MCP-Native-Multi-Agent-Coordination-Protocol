# 1. Python bağımlılıkları
pip install -r requirements.txt

# 2. Registry'yi başlat (terminalde açık kalacak)
cd mnacp
PYTHONPATH=.. python -m registry.server

# 3. Frontend'i başlat (ayrı terminal)
cd frontend
npm run dev
Hazır olunca uçtan uca testi çalıştıralım.