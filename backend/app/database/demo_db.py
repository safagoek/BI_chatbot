import sqlite3
import os
import random
from datetime import datetime, timedelta

DEMO_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "demo.db")

def init_demo_db():
    """Generates a demo SQLite database with realistic sales and customer records."""
    if os.path.exists(DEMO_DB_PATH):
        return  # Already created
        
    conn = sqlite3.connect(DEMO_DB_PATH)
    cursor = conn.cursor()
    
    # 1. Create customers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS musteriler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_soyad TEXT NOT NULL,
        sehir TEXT NOT NULL,
        kayit_tarihi DATE NOT NULL
    )
    """)
    
    # 2. Create sales table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS satislar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urun_adi TEXT NOT NULL,
        kategori TEXT NOT NULL,
        ciro REAL NOT NULL,
        adet INTEGER NOT NULL,
        tarih DATE NOT NULL,
        musteri_id INTEGER,
        FOREIGN KEY(musteri_id) REFERENCES musteriler(id)
    )
    """)
    
    # Insert Customers
    cities = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Adana"]
    first_names = ["Ahmet", "Mehmet", "Ayşe", "Fatma", "Can", "Elif", "Burak", "Selin", "Murat", "Ebru"]
    last_names = ["Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Yıldız", "Öztürk", "Aydın", "Aslan", "Polat"]
    
    customer_ids = []
    base_date = datetime(2025, 1, 1)
    
    for i in range(1, 21):
        ad_soyad = f"{random.choice(first_names)} {random.choice(last_names)}"
        sehir = random.choice(cities)
        kayit_tarihi = (base_date - timedelta(days=random.randint(10, 180))).strftime("%Y-%m-%d")
        cursor.execute("""
        INSERT INTO musteriler (ad_soyad, sehir, kayit_tarihi)
        VALUES (?, ?, ?)
        """, (ad_soyad, sehir, kayit_tarihi))
        customer_ids.append(i)
        
    # Insert Sales
    products = {
        "Teknoloji": [("Laptop Pro", 28000, 1), ("Akıllı Telefon", 15000, 1), ("Kablosuz Kulaklık", 1800, 2), ("Monitör 27 inç", 4500, 1)],
        "Ofis Malzemesi": [("Ergonomik Sandalye", 3500, 1), ("Yazı Tahtası", 850, 1), ("Kablosuz Klavye Mouse", 950, 2), ("Defter Seti", 250, 5)],
        "Giyim": [("Deri Ceket", 2400, 1), ("Spor Ayakkabı", 1900, 1), ("Klasik Gömlek", 600, 2), ("Termal Mont", 3200, 1)]
    }
    
    sales_date_start = datetime(2026, 1, 1)
    
    for _ in range(100):
        category = random.choice(list(products.keys()))
        prod_tuple = random.choice(products[category])
        urun_adi = prod_tuple[0]
        base_price = prod_tuple[1]
        max_qty = prod_tuple[2]
        
        adet = random.randint(1, max_qty + 2)
        ciro = base_price * adet * random.uniform(0.9, 1.1)  # introduce slight price variation
        ciro = round(ciro, 2)
        
        tarih = (sales_date_start + timedelta(days=random.randint(0, 140))).strftime("%Y-%m-%d")
        musteri_id = random.choice(customer_ids)
        
        cursor.execute("""
        INSERT INTO satislar (urun_adi, kategori, ciro, adet, tarih, musteri_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (urun_adi, category, ciro, adet, tarih, musteri_id))
        
    conn.commit()
    conn.close()
