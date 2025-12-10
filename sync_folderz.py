#!/usr/bin/env python3
"""Sync aanbiedingen van Folderz.nl naar de database - met promo types."""
import re
import requests
import psycopg2
from datetime import datetime, timedelta
from html import unescape

import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'supermarkt_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}

STORE_MAPPING = {
    'albert heijn': 'ah', 'ah': 'ah', 'jumbo': 'jumbo', 'lidl': 'lidl', 'aldi': 'aldi',
    'plus': 'plus', 'coop': 'coop', 'dekamarkt': 'dekamarkt', 'deka': 'dekamarkt',
    'dirk': 'dirk', 'vomar': 'vomar', 'vomar voordeelmarkt': 'vomar', 'hoogvliet': 'hoogvliet',
    'spar': 'spar', 'poiesz': 'poiesz', 'picnic': 'picnic', 'nettorama': 'nettorama',
    'jan linders': 'janlinders', 'boni': 'boni',
}

CATEGORIES = [
    # Vlees
    'gehakt', 'rundergehakt', 'kipgehakt', 'kip', 'kipfilet', 'kipdrumsticks',
    'biefstuk', 'entrecote', 'schnitzel', 'karbonade', 'riblappen', 'speklappen',
    'gehaktballen', 'hamburger', 'slavink', 'worst', 'rookworst', 'braadworst',
    'bacon', 'spek', 'ham', 'kalkoen', 'stoofvlees', 'gourmet', 'bbq',
    # Vis
    'vis', 'zalm', 'kabeljauw', 'tonijn', 'garnalen', 'mosselen', 'kibbeling',
    # Zuivel
    'melk', 'yoghurt', 'kwark', 'vla', 'kaas', 'boter', 'margarine', 'eieren', 'slagroom',
    # Brood
    'brood', 'croissant', 'stokbrood', 'crackers',
    # Groenten & fruit
    'groenten', 'sla', 'tomaten', 'komkommer', 'paprika', 'uien', 'wortel',
    'broccoli', 'champignons', 'aardappelen', 'krieltjes', 'friet',
    'fruit', 'appels', 'banaan', 'sinaasappel', 'druiven', 'aardbeien', 'mango',
    # Ontbijt
    'ontbijtgranen', 'muesli', 'havermout', 'pindakaas', 'jam', 'hagelslag', 'nutella',
    # Pasta & rijst
    'pasta', 'spaghetti', 'macaroni', 'penne', 'lasagne', 'rijst', 'noodles', 'couscous',
    # Sauzen & soep
    'saus', 'ketchup', 'mayonaise', 'mosterd', 'pesto', 'soep', 'bouillon',
    # Conserven
    'bonen', 'mais', 'passata',
    # Kant-en-klaar
    'maaltijd', 'pizza', 'ijs',
    # Dranken
    'frisdrank', 'cola', 'sap', 'sinaasappelsap', 'water', 'bier', 'wijn', 'koffie', 'thee',
    # Snacks
    'chips', 'noten', 'koek', 'chocolade', 'snoep', 'drop',
    # Huishouden
    'wasmiddel', 'afwasmiddel', 'schoonmaak', 'toiletpapier',
    # Verzorging
    'shampoo', 'tandpasta', 'deodorant',
]

def parse_price(price_str):
    if not price_str:
        return None
    price_str = re.sub(r'[^\d,.]', '', price_str)
    price_str = price_str.replace(',', '.')
    try:
        val = float(price_str)
        return val if val < 500 else None
    except:
        return None

def parse_promo_type(badge_text):
    """Parse de promo badge naar een leesbaar type"""
    if not badge_text:
        return None
    badge_lower = badge_text.lower().strip()
    
    # 1+1 gratis
    if '1+1' in badge_lower:
        return '1+1 gratis'
    # 2+1 gratis
    if '2+1' in badge_lower:
        return '2+1 gratis'
    # 2e halve prijs
    if '2e halve' in badge_lower or '2de halve' in badge_lower:
        return '2e halve prijs'
    # 2 voor X
    match = re.search(r'(\d+)\s*voor\s*(\d+[.,]?\d*)', badge_lower)
    if match:
        return f'{match.group(1)} voor {match.group(2)}'
    # X% korting
    pct_match = re.search(r'(\d+)\s*%', badge_text)
    if pct_match:
        return f'{pct_match.group(1)}% korting'
    
    return badge_text.strip()[:30] if badge_text.strip() else None

def fetch_category(category):
    url = f'https://www.folderz.nl/aanbiedingen/{category}'
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', 'Accept': 'text/html'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except:
        return None

def parse_products(html):
    products = []
    product_pattern = r'<div class="product">.*?</div>\s*</div>\s*</div>\s*</div>\s*</a>'
    product_blocks = re.findall(product_pattern, html, re.DOTALL)

    for block in product_blocks:
        product = {}

        # Store
        store_match = re.search(r'<img alt="([^"]+)"[^>]*class="[^"]*"[^>]*/?\s*>\s*</div>\s*<div class="shopping-list', block, re.DOTALL)
        if not store_match:
            store_match = re.search(r'class="store-image"[^>]*>.*?alt="([^"]+)"', block, re.DOTALL)
        if store_match:
            product['store'] = unescape(store_match.group(1).strip())

        # Name
        name_match = re.search(r'class="product__name[^"]*"[^>]*>\s*([^<]+)', block)
        if name_match:
            product['name'] = unescape(name_match.group(1).strip())

        # Price
        price_match = re.search(r'class="product__price-offer[^"]*"[^>]*>\s*([^<]+)', block)
        if price_match:
            product['price'] = parse_price(price_match.group(1))

        # Original price
        orig_match = re.search(r'class="product__price-normal[^"]*"[^>]*>\s*([^<]+)', block)
        if orig_match:
            product['original_price'] = parse_price(orig_match.group(1))

        # Badge (promo type) - NIEUW: bewaar de volledige tekst
        badge_match = re.search(r'class="badge badge--secondary">([^<]+)</div>', block)
        if badge_match:
            badge_text = badge_match.group(1)
            product['promo_type'] = parse_promo_type(badge_text)
            # Extract percentage if present
            pct_match = re.search(r'(\d+)\s*%', badge_text)
            if pct_match:
                product['badge_discount'] = int(pct_match.group(1))

        # Validity
        valid_match = re.search(r'class="product-date[^"]*"[^>]*>\s*([^<]+)', block)
        if valid_match:
            valid_text = valid_match.group(1)
            days_match = re.search(r'(\d+)\s*dag', valid_text)
            week_match = re.search(r'(\d+)\s*week', valid_text)
            if days_match:
                product['valid_days'] = int(days_match.group(1))
            elif week_match:
                product['valid_days'] = int(week_match.group(1)) * 7

        if product.get('name') and product.get('price') and product.get('store'):
            if product['price'] > 0:
                products.append(product)

    return products

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

        if not sm_code:
            continue

        name = p.get('name', '')
        price = p.get('price')
        original = p.get('original_price')
        valid_days = p.get('valid_days', 7)
        promo_type = p.get('promo_type')  # NIEUW

        discount_pct = None
        if original and original > price and original < price * 5:
            discount_pct = round((original - price) / original * 100)
        elif p.get('badge_discount'):
            discount_pct = p['badge_discount']
            if not original and discount_pct > 0 and discount_pct < 100:
                original = round(price / (1 - discount_pct / 100), 2)

        end_date = today + timedelta(days=valid_days)

        try:
            cur.execute('''
                INSERT INTO promotions
                (supermarket_code, product_name, original_price, discount_price, discount_percent, promo_type, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', (sm_code, name, original, price, discount_pct, promo_type, today, end_date))
            inserted += 1
        except:
            pass

    conn.commit()
    conn.close()
    return inserted

def main():
    print("=" * 60)
    print("Folderz.nl Aanbiedingen Sync (met promo types)")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM promotions WHERE promo_type IS NOT NULL OR promo_type = 'folder'")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Verwijderd: {deleted} oude aanbiedingen\n")

    total_products = []
    category_count = 0

    for category in CATEGORIES:
        html = fetch_category(category)
        if html:
            products = parse_products(html)
            if products:
                category_count += 1
                print(f"  {category:20} -> {len(products):3} producten")
                total_products.extend(products)

    print(f"\n{'-' * 60}")
    print(f"Categorieën: {category_count}/{len(CATEGORIES)}")
    print(f"Totaal: {len(total_products)} producten")

    # Deduplicate
    seen = set()
    unique = []
    for p in total_products:
        key = (p.get('store', '').lower(), p.get('name', '').lower())
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"Uniek: {len(unique)}")

    inserted = sync_to_database(unique)
    print(f"Geinserteerd: {inserted}")

    # Show promo types
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute('''
        SELECT promo_type, COUNT(*) as cnt 
        FROM promotions 
        WHERE promo_type IS NOT NULL 
        GROUP BY promo_type 
        ORDER BY cnt DESC 
        LIMIT 10
    ''')
    print(f"\nPromo types gevonden:")
    for row in cur.fetchall():
        print(f"  {row[0]:25} {row[1]:4}x")

    conn.close()
    print("=" * 60)

if __name__ == '__main__':
    main()
