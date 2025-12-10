#!/usr/bin/env python3
"""
Sync aanbiedingen van Folderz.nl naar de database.
Inclusief supermarkten EN drogisterijen.
"""
import re
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

# Mapping van Folderz winkel namen naar onze codes
STORE_MAPPING = {
    # === SUPERMARKTEN ===
    'albert heijn': 'ah',
    'ah': 'ah',
    'jumbo': 'jumbo',
    'lidl': 'lidl',
    'aldi': 'aldi',
    'plus': 'plus',
    'coop': 'coop',
    'dekamarkt': 'dekamarkt',
    'deka': 'dekamarkt',
    'dirk': 'dirk',
    'vomar': 'vomar',
    'vomar voordeelmarkt': 'vomar',
    'hoogvliet': 'hoogvliet',
    'spar': 'spar',
    'poiesz': 'poiesz',
    'picnic': 'picnic',
    'nettorama': 'nettorama',
    'jan linders': 'janlinders',
    'boni': 'boni',
    'ekoplaza': 'ekoplaza',

    # === DROGISTERIJEN ===
    'kruidvat': 'kruidvat',
    'etos': 'etos',
    'trekpleister': 'trekpleister',
    'da': 'da',
    'holland & barrett': 'hollandbarrett',
    'holland &amp; barrett': 'hollandbarrett',
    'douglas': 'douglas',
    'de online drogist': 'onlinedrogist',
}

# Supermarkt categorieën
SUPERMARKT_CATEGORIES = [
    # === VLEES ===
    'gehakt', 'rundergehakt', 'kipgehakt',
    'kip', 'kipfilet', 'kipdrumsticks', 'kippenvleugels',
    'rund', 'rundvlees', 'biefstuk', 'entrecote',
    'speklappen', 'karbonade', 'riblappen',
    'gehaktballen', 'hamburger', 'slavink',
    'worst', 'rookworst', 'braadworst',
    'bacon', 'spek', 'ham', 'achterham',
    'schnitzel', 'kalkoen', 'stoofvlees',
    'gourmet', 'bbq',

    # === VIS ===
    'vis', 'zalm', 'kabeljauw', 'tonijn',
    'garnalen', 'mosselen', 'haring', 'kibbeling',

    # === ZUIVEL ===
    'melk', 'karnemelk',
    'yoghurt', 'kwark', 'vla', 'pudding',
    'kaas', 'goudse-kaas', 'oude-kaas',
    'roomboter', 'boter', 'margarine',
    'eieren', 'slagroom',

    # === BROOD ===
    'brood', 'volkoren', 'croissant', 'stokbrood',
    'beschuit', 'crackers', 'toast',

    # === GROENTEN ===
    'groenten', 'sla', 'tomaten', 'komkommer',
    'paprika', 'uien', 'wortel', 'broccoli', 'bloemkool',
    'spinazie', 'champignons',
    'aardappelen', 'krieltjes', 'friet',

    # === FRUIT ===
    'fruit', 'appels', 'peren', 'banaan',
    'sinaasappel', 'mandarijnen', 'druiven',
    'aardbeien', 'frambozen', 'ananas', 'mango',

    # === ONTBIJT & BELEG ===
    'ontbijtgranen', 'muesli', 'cornflakes', 'havermout',
    'pindakaas', 'jam', 'hagelslag', 'nutella',

    # === PASTA, RIJST ===
    'pasta', 'spaghetti', 'macaroni', 'penne', 'lasagne',
    'rijst', 'noodles', 'couscous',

    # === SAUZEN & SOEPEN ===
    'saus', 'ketchup', 'mayonaise', 'mosterd',
    'soep', 'bouillon',

    # === CONSERVEN ===
    'bonen', 'erwten', 'mais',

    # === KANT-EN-KLAAR & DIEPVRIES ===
    'maaltijd', 'pizza', 'ijs',

    # === DRANKEN ===
    'frisdrank', 'cola', 'fanta',
    'sap', 'sinaasappelsap', 'appelsap',
    'water', 'spa',
    'bier', 'wijn',
    'koffie', 'thee',

    # === SNACKS & SNOEP ===
    'chips', 'noten',
    'koek', 'chocolade', 'snoep', 'drop',

    # === HUISHOUDEN ===
    'wasmiddel', 'wasverzachter', 'afwasmiddel',
    'schoonmaak', 'toiletpapier', 'tissues',
]

# Drogisterij categorieën
DROGIST_CATEGORIES = [
    # === HAARVERZORGING ===
    'shampoo', 'conditioner', 'haarmasker', 'haargel',
    'haarspray', 'haarlak', 'haarverf', 'haarserum',

    # === HUIDVERZORGING ===
    'dagcreme', 'nachtcreme', 'gezichtscreme', 'bodylotion',
    'handcreme', 'zonnebrand', 'aftersun', 'lippenbalsem',
    'gezichtsmasker', 'scrub', 'reinigingsmelk', 'tonic',

    # === MONDVERZORGING ===
    'tandpasta', 'tandenborstel', 'mondwater', 'flosdraad',

    # === LICHAAMSVERZORGING ===
    'deodorant', 'douchegel', 'douchecreme', 'zeep', 'badschuim',
    'scheerschuim', 'scheermesjes', 'aftershave',

    # === MAKE-UP ===
    'mascara', 'lippenstift', 'lipgloss', 'foundation',
    'concealer', 'oogschaduw', 'eyeliner', 'nagellak',
    'make-up-remover', 'primer',

    # === PARFUM ===
    'parfum', 'eau-de-toilette', 'bodyspray',

    # === BABY & KIND ===
    'luiers', 'babydoekjes', 'babyshampoo', 'babycreme',
    'flesvoeding', 'fruithapje',

    # === GEZONDHEID ===
    'vitamines', 'vitamine-c', 'vitamine-d', 'multivitaminen',
    'paracetamol', 'ibuprofen', 'neusspray', 'hoestdrank',
    'pleister', 'verband', 'thermometer',

    # === HYGIENE ===
    'maandverband', 'tampons', 'inlegkruisjes',
    'wattenschijfjes', 'wattenstaafjes',

    # === HUISHOUD (drogist) ===
    'wasmiddel', 'wasverzachter', 'vlekkenverwijderaar',
    'allesreiniger', 'glasreiniger', 'toiletblok',
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

def ensure_stores_exist(conn):
    """Zorg dat alle drogisterijen in de supermarkets tabel staan"""
    cur = conn.cursor()

    drogist_stores = [
        ('kruidvat', 'Kruidvat', '💊'),
        ('etos', 'Etos', '💄'),
        ('trekpleister', 'Trekpleister', '🏪'),
        ('da', 'DA Drogist', '💊'),
        ('hollandbarrett', 'Holland & Barrett', '🌿'),
        ('douglas', 'Douglas', '💐'),
        ('onlinedrogist', 'De Online Drogist', '📦'),
        ('ekoplaza', 'Ekoplaza', '🌱'),
    ]

    for code, name, icon in drogist_stores:
        cur.execute('''
            INSERT INTO supermarkets (code, name, icon)
            VALUES (%s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET name = %s, icon = %s
        ''', (code, name, icon, name, icon))

    conn.commit()
    print(f"Drogisterijen toegevoegd/bijgewerkt in database")

def sync_to_database(products, promo_type='folder'):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    today = datetime.now().date()
    inserted = 0
    store_counts = {}

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
            ''', (sm_code, name, original, price, discount_pct, promo_type, today, end_date))
            inserted += 1
            store_counts[sm_code] = store_counts.get(sm_code, 0) + 1
        except Exception as e:
            pass

    conn.commit()
    conn.close()
    return inserted, store_counts

def main():
    print("=" * 70)
    print("FOLDERZ.NL SYNC - SUPERMARKTEN & DROGISTERIJEN")
    print("=" * 70)

    # Ensure drogist stores exist
    conn = psycopg2.connect(**DB_CONFIG)
    ensure_stores_exist(conn)

    # Clear old promotions
    cur = conn.cursor()
    cur.execute("DELETE FROM promotions WHERE promo_type = 'folder'")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Verwijderd: {deleted} oude folder aanbiedingen\n")

    # === SUPERMARKTEN ===
    print("-" * 70)
    print("SUPERMARKT AANBIEDINGEN")
    print("-" * 70)

    supermarkt_products = []
    sm_category_count = 0

    for category in SUPERMARKT_CATEGORIES:
        html = fetch_category(category)
        if html:
            products = parse_products(html)
            if products:
                sm_category_count += 1
                print(f"  {category:25} -> {len(products):3} producten")
                supermarkt_products.extend(products)

    print(f"\nSupermarkt categorieën: {sm_category_count}/{len(SUPERMARKT_CATEGORIES)}")
    print(f"Supermarkt producten gevonden: {len(supermarkt_products)}")

    # === DROGISTERIJEN ===
    print("\n" + "-" * 70)
    print("DROGISTERIJ AANBIEDINGEN")
    print("-" * 70)

    drogist_products = []
    dr_category_count = 0

    for category in DROGIST_CATEGORIES:
        html = fetch_category(category)
        if html:
            products = parse_products(html)
            if products:
                dr_category_count += 1
                print(f"  {category:25} -> {len(products):3} producten")
                drogist_products.extend(products)

    print(f"\nDrogist categorieën: {dr_category_count}/{len(DROGIST_CATEGORIES)}")
    print(f"Drogist producten gevonden: {len(drogist_products)}")

    # Combine and deduplicate
    all_products = supermarkt_products + drogist_products

    seen = set()
    unique = []
    for p in all_products:
        key = (p.get('store', '').lower(), p.get('name', '').lower())
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"\n{'=' * 70}")
    print(f"TOTAAL: {len(unique)} unieke producten")
    print("=" * 70)

    inserted, store_counts = sync_to_database(unique)

    print(f"\nGeïnserteerd: {inserted} promoties")
    print("\nPer winkel:")
    for store, count in sorted(store_counts.items(), key=lambda x: -x[1]):
        print(f"  {store:15} {count:4} aanbiedingen")

    # Show top deals
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print(f"\n{'=' * 70}")
    print("TOP DROGISTERIJ DEALS")
    print("=" * 70)

    # Drogist winkels
    drogist_codes = ['kruidvat', 'etos', 'trekpleister', 'da', 'hollandbarrett', 'douglas']

    cur.execute('''
        SELECT supermarket_code, product_name, discount_price, discount_percent
        FROM promotions
        WHERE promo_type = 'folder'
        AND discount_percent IS NOT NULL
        AND supermarket_code = ANY(%s)
        ORDER BY discount_percent DESC
        LIMIT 15
    ''', (drogist_codes,))

    for row in cur.fetchall():
        print(f"  {row[0]:12} {row[1][:40]:40} €{row[2]:.2f} (-{row[3]}%)")

    # Summary
    cur.execute('SELECT COUNT(*) FROM promotions WHERE promo_type = %s', ('folder',))
    total = cur.fetchone()[0]

    cur.execute('''
        SELECT COUNT(*) FROM promotions
        WHERE promo_type = 'folder' AND supermarket_code = ANY(%s)
    ''', (drogist_codes,))
    drogist_total = cur.fetchone()[0]

    print(f"\n{'=' * 70}")
    print(f"TOTAAL IN DATABASE: {total} folder aanbiedingen")
    print(f"  - Supermarkten: {total - drogist_total}")
    print(f"  - Drogisterijen: {drogist_total}")
    print("=" * 70)

    conn.close()

if __name__ == '__main__':
    main()
