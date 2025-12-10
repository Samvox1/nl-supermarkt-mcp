#!/usr/bin/env python3
import httpx
import psycopg2
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'supermarkt_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}

SUPERMARKETS_META = {
    'ah': {'name': 'Albert Heijn', 'icon': '🟦'},
    'jumbo': {'name': 'Jumbo', 'icon': '🟨'},
    'aldi': {'name': 'Aldi', 'icon': '🟧'},
    'lidl': {'name': 'Lidl', 'icon': '🟦'},
    'plus': {'name': 'Plus', 'icon': '🟩'},
    'deka': {'name': 'DekaMarkt', 'icon': '🟥'},
    'vomar': {'name': 'Vomar', 'icon': '🟧'},
    'dirk': {'name': 'Dirk', 'icon': '🟥'},
    'coop': {'name': 'Coop', 'icon': '🟩'},
    'hoogvliet': {'name': 'Hoogvliet', 'icon': '🟧'},
    'spar': {'name': 'Spar', 'icon': '🟩'},
    'picnic': {'name': 'Picnic', 'icon': '🟨'},
}

def fetch_data():
    logger.info('Fetching data from Checkjebon.nl...')
    response = httpx.get('https://www.checkjebon.nl/data/supermarkets.json',
        headers={'User-Agent': 'NL-Supermarkt-MCP/1.0'}, timeout=60.0)
    response.raise_for_status()
    return response.json()

def sync_to_db(data):
    logger.info('Syncing to PostgreSQL...')
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    for sm in data:
        code = sm.get('n', '')
        meta = SUPERMARKETS_META.get(code, {'name': code.title(), 'icon': '🏪'})
        cur.execute('''INSERT INTO supermarkets (code, name, icon) VALUES (%s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, icon = EXCLUDED.icon''',
            (code, meta['name'], meta['icon']))
    
    total_products = 0
    for sm in data:
        sm_code = sm.get('n', '')
        products = sm.get('d', [])
        if not products:
            continue
        
        seen = set()
        for p in products:
            name = p.get('n', '')
            price = p.get('p', 0)
            unit = p.get('s', '')
            link = p.get('l', '')
            key = (sm_code, name)
            if name and price and key not in seen:
                seen.add(key)
                cur.execute('''INSERT INTO products (supermarket_code, name, price, unit, link, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (supermarket_code, name) DO UPDATE SET 
                    price = EXCLUDED.price, unit = EXCLUDED.unit, link = EXCLUDED.link, updated_at = EXCLUDED.updated_at''',
                    (sm_code, name, price, unit, link, datetime.now()))
                total_products += 1
        
        logger.info(f'  {sm_code}: {len(seen)} products')
    
    cur.execute('''INSERT INTO price_history (product_id, price)
        SELECT p.id, p.price FROM products p
        WHERE NOT EXISTS (SELECT 1 FROM price_history ph WHERE ph.product_id = p.id AND DATE(ph.recorded_at) = CURRENT_DATE)''')
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f'Synced {total_products} products total')

def main():
    try:
        data = fetch_data()
        sync_to_db(data)
        logger.info('Sync completed successfully!')
    except Exception as e:
        logger.error(f'Sync failed: {e}')
        raise

if __name__ == '__main__':
    main()
