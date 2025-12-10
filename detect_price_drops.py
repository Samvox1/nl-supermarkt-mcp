#!/usr/bin/env python3
"""
Detecteer prijsdalingen door huidige prijzen te vergelijken met recente historie.
Vul de promotions tabel met producten die in prijs zijn gedaald.
"""
import psycopg2
from datetime import datetime, timedelta

DB_CONFIG = {
    'database': 'supermarkt_db',
    'user': 'postgres',
    'port': 5433,
    'host': '127.0.0.1'
}

def detect_price_drops():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Eerst oude detecties opruimen
    cur.execute("DELETE FROM promotions WHERE promo_type = 'prijsdaling'")
    
    # Vind producten waar de huidige prijs lager is dan de vorige prijs
    # We vergelijken de laatste 2 prijspunten
    cur.execute("""
        WITH price_changes AS (
            SELECT 
                p.id as product_id,
                p.supermarket_code,
                p.name,
                p.price as current_price,
                p.link,
                LAG(ph.price) OVER (PARTITION BY p.id ORDER BY ph.recorded_at DESC) as previous_price,
                ph.recorded_at
            FROM products p
            JOIN price_history ph ON p.id = ph.product_id
        ),
        price_drops AS (
            SELECT DISTINCT ON (product_id)
                supermarket_code,
                name,
                previous_price as original_price,
                current_price as discount_price,
                ROUND(((previous_price - current_price) / previous_price * 100)::numeric, 0) as discount_percent
            FROM price_changes
            WHERE previous_price IS NOT NULL 
              AND current_price < previous_price
              AND previous_price > 0
              AND ((previous_price - current_price) / previous_price * 100) >= 5  -- Minimaal 5% korting
            ORDER BY product_id, recorded_at DESC
        )
        SELECT * FROM price_drops
        WHERE discount_percent <= 80  -- Filter onrealistische kortingen
        ORDER BY discount_percent DESC
        LIMIT 500
    """)
    
    drops = cur.fetchall()
    print(f"Gevonden: {len(drops)} prijsdalingen")
    
    # Insert als promoties
    today = datetime.now().date()
    end_date = today + timedelta(days=7)  # Geldig voor 7 dagen
    
    inserted = 0
    for drop in drops:
        supermarket_code, name, original_price, discount_price, discount_percent = drop
        try:
            cur.execute("""
                INSERT INTO promotions 
                (supermarket_code, product_name, original_price, discount_price, discount_percent, promo_type, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, 'prijsdaling', %s, %s)
                ON CONFLICT DO NOTHING
            """, (supermarket_code, name, float(original_price), float(discount_price), int(discount_percent), today, end_date))
            inserted += 1
        except Exception as e:
            print(f"Error inserting {name}: {e}")
    
    conn.commit()
    print(f"Geinserteerd: {inserted} promoties")
    
    # Toon top 10
    cur.execute("""
        SELECT supermarket_code, product_name, original_price, discount_price, discount_percent
        FROM promotions
        WHERE promo_type = 'prijsdaling'
        ORDER BY discount_percent DESC
        LIMIT 10
    """)
    print("\nTop 10 prijsdalingen:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} - was €{row[2]:.2f}, nu €{row[3]:.2f} ({row[4]}% korting)")
    
    conn.close()

if __name__ == '__main__':
    detect_price_drops()
