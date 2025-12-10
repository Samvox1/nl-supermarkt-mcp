#!/usr/bin/env python3
"""
Sync aanbiedingen van Folderz.nl naar de database.
Inclusief supermarkten EN drogisterijen.
"""
import os
import re
import time
import requests
import psycopg2
from datetime import datetime, timedelta
from html import unescape

# Gebruik environment variables met correcte defaults voor Docker
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'db'),
    'port': int(os.environ.get('DB_PORT', '5432')),
    'database': os.environ.get('DB_NAME', 'supermarkt_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'supermarkt123')
}

# Mapping van Folderz winkel namen naar onze codes
STORE_MAPPING = {
    # === SUPERMARKTEN ===
    'albert heijn': 'ah', 'ah': 'ah',
    'jumbo': 'jumbo', 'lidl': 'lidl', 'aldi': 'aldi',
    'plus': 'plus', 'coop': 'coop',
    'dekamarkt': 'dekamarkt', 'deka': 'dekamarkt',
    'dirk': 'dirk', 'vomar': 'vomar', 'vomar voordeelmarkt': 'vomar',
    'hoogvliet': 'hoogvliet', 'spar': 'spar', 'poiesz': 'poiesz',
    'picnic': 'picnic', 'nettorama': 'nettorama',
    'jan linders': 'janlinders', 'boni': 'boni', 'ekoplaza': 'ekoplaza',
    # === DROGISTERIJEN ===
    'kruidvat': 'kruidvat', 'etos': 'etos', 'trekpleister': 'trekpleister',
    'da': 'da', 'holland & barrett': 'hollandbarrett',
    'holland &amp; barrett': 'hollandbarrett',
    'douglas': 'douglas', 'de online drogist': 'onlinedrogist',
}

SUPERMARKT_CATEGORIES = [
    'gehakt', 'kip', 'kipfilet', 'rund', 'biefstuk', 'worst', 'rookworst',
    'bacon', 'spek', 'ham', 'schnitzel', 'kalkoen', 'gourmet', 'bbq',
    'vis', 'zalm', 'tonijn', 'garnalen', 'haring',
    'melk', 'yoghurt', 'kwark', 'vla', 'kaas', 'boter', 'eieren', 'slagroom',
    'brood', 'croissant', 'crackers',
    'groenten', 'tomaten', 'paprika', 'broccoli', 'aardappelen', 'friet',
    'fruit', 'appels', 'banaan', 'sinaasappel', 'aardbeien', 'ananas', 'mango',
    'muesli', 'pindakaas', 'jam', 'hagelslag', 'nutella',
    'pasta', 'spaghetti', 'rijst', 'noodles',
    'saus', 'ketchup', 'mayonaise', 'soep',
    'pizza', 'ijs',
    'frisdrank', 'cola', 'sap', 'water', 'bier', 'wijn', 'koffie', 'thee',
    'chips', 'noten', 'koek', 'chocolade', 'drop',
    'wasmiddel', 'wasverzachter', 'toiletpapier', 'tissues',
]

DROGIST_CATEGORIES = [
    'luiers', 'pampers', 'babydoekjes',
    'tandpasta', 'tandenborstel', 'tandenstokers', 'mondwater',
    'deodorant', 'douchegel', 'scheermesjes',
    'shampoo', 'conditioner', 'haarverf',
    'dagcreme', 'bodylotion', 'zonnebrand',
    'mascara', 'parfum', 'vitamines',
    'maandverband', 'tampons',
]

def parse_price(price_str):
    if not price_str: return None
    price_str = re.sub(r'[^\d,.]', '', price_str).replace(',', '.')
    try:
        val = float(price_str)
        return val if val < 500 else None
    except: return None

def fetch_category(category):
    url = f'https://www.folderz.nl/aanbiedingen/{category}'
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 404: return None
        response.raise_for_status()
        return response.text
    except: return None

def parse_products(html):
    products = []
    product_pattern = r'<div class="product">.*?</div>\s*</div>\s*</div>\s*</div>\s*</a>'
    for block in re.findall(product_pattern, html, re.DOTALL):
        product = {}
        store_match = re.search(r'<img alt="([^"]+)"[^>]*class="[^"]*"[^>]*/?\s*>\s*</div>\s*<div class="shopping-list', block, re.DOTALL)
        if not store_match:
            store_match = re.search(r'class="store-image"[^>]*>.*?alt="([^"]+)"', block, re.DOTALL)
        if store_match: product['store'] = unescape(store_match.group(1).strip())
        name_match = re.search(r'class="product__name[^"]*"[^>]*>\s*([^<]+)', block)
        if name_match: product['name'] = unescape(name_match.group(1).strip())
        price_match = re.search(r'class="product__price-offer[^"]*"[^>]*>\s*([^<]+)', block)
        if price_match: product['price'] = parse_price(price_match.group(1))
        orig_match = re.search(r'class="product__price-normal[^"]*"[^>]*>\s*([^<]+)', block)
        if orig_match: product['original_price'] = parse_price(orig_match.group(1))
        badge_match = re.search(r'class="badge badge--secondary">([^<]+)</div>', block)
        if badge_match:
            pct_match = re.search(r'(\d+)\s*%', badge_match.group(1))
            if pct_match: product['badge_discount'] = int(pct_match.group(1))
        valid_match = re.search(r'class="product-date[^"]*"[^>]*>\s*([^<]+)', block)
        if valid_match:
            valid_text = valid_match.group(1)
            days_match = re.search(r'(\d+)\s*dag', valid_text)
            week_match = re.search(r'(\d+)\s*week', valid_text)
            if days_match: product['valid_days'] = int(days_match.group(1))
            elif week_match: product['valid_days'] = int(week_match.group(1)) * 7
        if product.get('name') and product.get('price') and product.get('store'):
            if product['price'] > 0: products.append(product)
    return products

def ensure_drogist_stores():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    stores = [
        ('kruidvat', 'Kruidvat', '💊'), ('etos', 'Etos', '💄'),
        ('trekpleister', 'Trekpleister', '🏪'), ('da', 'DA Drogist', '💊'),
        ('hollandbarrett', 'Holland & Barrett', '🌿'), ('douglas', 'Douglas', '💐'),
        ('onlinedrogist', 'De Online Drogist', '📦'), ('ekoplaza', 'Ekoplaza', '🌱'),
    ]
    for code, name, icon in stores:
        cur.execute('INSERT INTO supermarkets (code, name, icon) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET name = %s, icon = %s', (code, name, icon, name, icon))
    conn.commit()
    conn.close()
    print('Drogisterijen toegevoegd/bijgewerkt in database')

def sync_to_database(products):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    today = datetime.now().date()
    inserted = 0
    for p in products:
        store_name = p.get('store', '').lower()
        sm_code = None
        for pattern, code in STORE_MAPPING.items():
            if pattern in store_name:
                sm_code = code
                break
        if not sm_code: continue
        name, price = p.get('name', ''), p.get('price')
        original, valid_days = p.get('original_price'), p.get('valid_days', 7)
        discount_pct = None
        if original and original > price and original < price * 5:
            discount_pct = round((original - price) / original * 100)
        elif p.get('badge_discount'):
            discount_pct = p['badge_discount']
            if not original and discount_pct > 0 and discount_pct < 100:
                original = price / (1 - discount_pct / 100)
        end_date = today + timedelta(days=valid_days)
        try:
            cur.execute('INSERT INTO promotions (supermarket_code, product_name, original_price, discount_price, discount_percent, promo_type, start_date, end_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING', (sm_code, name, original, price, discount_pct, 'folder', today, end_date))
            if cur.rowcount > 0: inserted += 1
        except: pass
    conn.commit()
    conn.close()
    return inserted

def main():
    print('=' * 70)
    print('FOLDERZ.NL SYNC - SUPERMARKTEN & DROGISTERIJEN')
    print('=' * 70)
    ensure_drogist_stores()
    
    # Clear old promotions
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM promotions WHERE promo_type = 'folder'")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    print(f'Verwijderd: {deleted} oude folder aanbiedingen\n')
    
    all_products = []
    
    # Supermarkten
    print('-' * 70)
    print('SUPERMARKT AANBIEDINGEN')
    print('-' * 70)
    for i, cat in enumerate(SUPERMARKT_CATEGORIES):
        html = fetch_category(cat)
        if html:
            prods = parse_products(html)
            if prods:
                print(f'  {cat:25} -> {len(prods):3} producten')
                all_products.extend(prods)
        time.sleep(0.2)
        if i > 0 and i % 20 == 0: time.sleep(1)
    
    print('\nWachten voor drogist sync...')
    time.sleep(3)
    
    # Drogisterijen
    print('\n' + '-' * 70)
    print('DROGISTERIJ AANBIEDINGEN')
    print('-' * 70)
    for i, cat in enumerate(DROGIST_CATEGORIES):
        html = fetch_category(cat)
        if html:
            prods = parse_products(html)
            if prods:
                print(f'  {cat:25} -> {len(prods):3} producten')
                all_products.extend(prods)
        time.sleep(0.5)
        if i > 0 and i % 10 == 0: time.sleep(2)
    
    # Deduplicate
    seen, unique = set(), []
    for p in all_products:
        key = (p.get('store', '').lower(), p.get('name', '').lower())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    print(f'\n{"=" * 70}')
    print(f'TOTAAL: {len(unique)} unieke producten')
    print('=' * 70)
    
    inserted = sync_to_database(unique)
    print(f'\nGeïnserteerd: {inserted} promoties')
    
    # Stats per winkel
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT supermarket_code, COUNT(*) FROM promotions WHERE promo_type = 'folder' GROUP BY supermarket_code ORDER BY COUNT(*) DESC")
    print('\nPer winkel:')
    for row in cur.fetchall():
        print(f'  {row[0]:16} {row[1]:3} aanbiedingen')
    
    # Drogist top deals
    DROGIST_CODES = ['kruidvat', 'etos', 'trekpleister', 'da', 'hollandbarrett', 'douglas', 'onlinedrogist']
    cur.execute("SELECT supermarket_code, product_name, discount_price, discount_percent FROM promotions WHERE promo_type = 'folder' AND supermarket_code = ANY(%s) AND discount_percent IS NOT NULL ORDER BY discount_percent DESC LIMIT 15", (DROGIST_CODES,))
    print(f'\n{"=" * 70}')
    print('TOP DROGISTERIJ DEALS')
    print('=' * 70)
    for row in cur.fetchall():
        print(f'  {row[0]:12} {row[1][:40]:40} €{row[2]:.2f} (-{row[3]}%)')
    
    # Totals
    cur.execute("SELECT COUNT(*) FROM promotions WHERE promo_type = 'folder'")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM promotions WHERE promo_type = 'folder' AND supermarket_code = ANY(%s)", (DROGIST_CODES,))
    drogist_count = cur.fetchone()[0]
    print(f'\n{"=" * 70}')
    print(f'TOTAAL IN DATABASE: {total} folder aanbiedingen')
    print(f'  - Supermarkten: {total - drogist_count}')
    print(f'  - Drogisterijen: {drogist_count}')
    print('=' * 70)
    conn.close()

if __name__ == '__main__':
    main()
