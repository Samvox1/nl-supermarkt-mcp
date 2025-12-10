#!/usr/bin/env python3
"""
Sync alleen drogisterij aanbiedingen van Folderz.nl - met langere delays
"""
import re
import time
import requests
import psycopg2
from datetime import datetime, timedelta
from html import unescape

DB_CONFIG = {
    'database': 'supermarkt_db',
    'user': 'postgres',
    'port': 5433,
    'host': '127.0.0.1'
}

STORE_MAPPING = {
    'kruidvat': 'kruidvat',
    'etos': 'etos',
    'trekpleister': 'trekpleister',
    'da': 'da',
    'holland & barrett': 'hollandbarrett',
    'holland &amp; barrett': 'hollandbarrett',
    'douglas': 'douglas',
    'de online drogist': 'onlinedrogist',
    # Supermarkten ook mappen (sommige drogist producten zitten daar)
    'albert heijn': 'ah',
    'ah': 'ah',
    'jumbo': 'jumbo',
    'lidl': 'lidl',
    'aldi': 'aldi',
    'plus': 'plus',
    'dirk': 'dirk',
}

DROGIST_CATEGORIES = [
    # === MONDVERZORGING ===
    'tandpasta', 'tandenborstel', 'tandenstokers', 'mondwater',

    # === LICHAAMSVERZORGING ===
    'deodorant', 'douchegel', 'handzeep', 'scheermesjes', 'scheerschuim', 'aftershave',

    # === HAARVERZORGING ===
    'shampoo', 'conditioner', 'haarverf',

    # === HUIDVERZORGING ===
    'dagcreme', 'bodylotion', 'zonnebrand', 'aftersun', 'lippenbalsem',

    # === MAKE-UP ===
    'mascara', 'eyeliner', 'oogschaduw', 'lippenstift', 'lipgloss', 'foundation', 'nagellak',

    # === PARFUM ===
    'parfum',

    # === GEZONDHEID ===
    'vitamines', 'hoestdrank', 'neusspray', 'pleister', 'oogdruppels',

    # === OOGZORG ===
    'lenzen', 'contactlenzen',

    # === HYGIENE ===
    'maandverband', 'tampons', 'wattenschijfjes',
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

def fetch_category(category):
    url = f'https://www.folderz.nl/aanbiedingen/{category}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  Error: {e}")
        return None

def parse_products(html):
    products = []
    product_pattern = r'<div class="product">.*?</div>\s*</div>\s*</div>\s*</div>\s*</a>'
    product_blocks = re.findall(product_pattern, html, re.DOTALL)

    for block in product_blocks:
        product = {}

        store_match = re.search(r'<img alt="([^"]+)"[^>]*class="[^"]*"[^>]*/?\s*>\s*</div>\s*<div class="shopping-list', block, re.DOTALL)
        if not store_match:
            store_match = re.search(r'class="store-image"[^>]*>.*?alt="([^"]+)"', block, re.DOTALL)
        if store_match:
            product['store'] = unescape(store_match.group(1).strip())

        name_match = re.search(r'class="product__name[^"]*"[^>]*>\s*([^<]+)', block)
        if name_match:
            product['name'] = unescape(name_match.group(1).strip())

        price_match = re.search(r'class="product__price-offer[^"]*"[^>]*>\s*([^<]+)', block)
        if price_match:
            product['price'] = parse_price(price_match.group(1))

        orig_match = re.search(r'class="product__price-normal[^"]*"[^>]*>\s*([^<]+)', block)
        if orig_match:
            product['original_price'] = parse_price(orig_match.group(1))

        badge_match = re.search(r'class="badge badge--secondary">([^<]+)</div>', block)
        if badge_match:
            badge_text = badge_match.group(1)
            pct_match = re.search(r'(\d+)\s*%', badge_text)
            if pct_match:
                product['badge_discount'] = int(pct_match.group(1))

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

        discount_pct = None
        if original and original > price and original < price * 5:
            discount_pct = round((original - price) / original * 100)
        elif p.get('badge_discount'):
            discount_pct = p['badge_discount']
            if not original and discount_pct > 0 and discount_pct < 100:
                original = price / (1 - discount_pct / 100)

        end_date = today + timedelta(days=valid_days)

        try:
            cur.execute('''
                INSERT INTO promotions
                (supermarket_code, product_name, original_price, discount_price, discount_percent, promo_type, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', (sm_code, name, original, price, discount_pct, 'folder', today, end_date))
            if cur.rowcount > 0:
                inserted += 1
        except:
            pass

    conn.commit()
    conn.close()
    return inserted

def main():
    print("=" * 60)
    print("DROGISTERIJ SYNC - met lange delays")
    print("=" * 60)

    all_products = []

    for i, category in enumerate(DROGIST_CATEGORIES):
        print(f"[{i+1}/{len(DROGIST_CATEGORIES)}] Fetching {category}...", end=" ", flush=True)

        html = fetch_category(category)
        if html:
            products = parse_products(html)
            if products:
                print(f"{len(products)} producten")
                all_products.extend(products)
            else:
                print("0 producten")
        else:
            print("FAILED")

        # 2 seconden tussen elke request
        time.sleep(2)

    # Deduplicate
    seen = set()
    unique = []
    for p in all_products:
        key = (p.get('store', '').lower(), p.get('name', '').lower())
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"\nTotaal: {len(unique)} unieke producten")

    inserted = sync_to_database(unique)
    print(f"Nieuw geinserteerd: {inserted}")

    # Toon tandenstokers
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute('''
        SELECT supermarket_code, product_name, discount_price, discount_percent
        FROM promotions
        WHERE product_name ILIKE '%tandenstoker%' OR product_name ILIKE '%floss%'
        ORDER BY discount_percent DESC NULLS LAST
        LIMIT 10
    ''')
    print("\nTANDENSTOKERS & FLOSS:")
    for row in cur.fetchall():
        pct = f"-{row[3]}%" if row[3] else ""
        print(f"  {row[0]:12} {row[1][:40]:40} €{row[2]:.2f} {pct}")
    conn.close()

if __name__ == '__main__':
    main()
