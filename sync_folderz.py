#!/usr/bin/env python3
import os, re, time, random, requests, psycopg2
from datetime import datetime, timedelta
from html import unescape

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "database": os.environ.get("DB_NAME", "supermarkt_db"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "supermarkt123")
}

STORE_MAPPING = {
    "albert heijn": "ah", "ah": "ah", "jumbo": "jumbo", "lidl": "lidl",
    "aldi": "aldi", "plus": "plus", "coop": "coop", "dekamarkt": "dekamarkt",
    "dirk": "dirk", "vomar": "vomar", "hoogvliet": "hoogvliet", "spar": "spar",
    "poiesz": "poiesz", "nettorama": "nettorama", "boni": "boni", "ekoplaza": "ekoplaza",
    "kruidvat": "kruidvat", "etos": "etos", "trekpleister": "trekpleister",
    "da": "da", "holland & barrett": "hollandbarrett", "holland &amp; barrett": "hollandbarrett",
    "douglas": "douglas", "de online drogist": "onlinedrogist", "makro": "makro",
}

CATEGORIES = [
    "gehakt", "kip", "kipfilet", "rund", "biefstuk", "worst", "rookworst",
    "bacon", "spek", "ham", "schnitzel", "kalkoen", "gourmet", "bbq",
    "vis", "zalm", "tonijn", "garnalen", "haring",
    "melk", "yoghurt", "kwark", "vla", "kaas", "boter", "eieren", "slagroom",
    "campina", "danone", "almhof", "mona",
    "brood", "croissant", "crackers",
    "groenten", "tomaten", "paprika", "broccoli", "aardappelen", "friet",
    "komkommer", "wortel", "spinazie", "bloemkool",
    "fruit", "appels", "banaan", "sinaasappel", "aardbeien", "ananas", "mango", "druiven", "kiwi",
    "muesli", "pindakaas", "jam", "hagelslag", "nutella", "havermout",
    "pasta", "spaghetti", "rijst", "noodles",
    "saus", "ketchup", "mayonaise", "soep", "heinz", "unox", "knorr",
    "pizza", "ijs", "magnum",
    "frisdrank", "cola", "sap", "water", "koffie", "thee",
    "coca-cola", "pepsi", "fanta", "sprite", "lipton", "red-bull", "chocomel",
    "bier", "heineken", "grolsch", "hertog-jan", "amstel", "bavaria", "jupiler", "brand",
    "warsteiner", "desperados", "affligem", "leffe", "corona", "radler", "wijn",
    "douwe-egberts", "nespresso", "senseo",
    "chips", "noten", "koek", "chocolade", "drop", "snoep",
    "lays", "doritos", "pringles", "oreo", "milka", "kitkat", "mars", "haribo",
    "wasmiddel", "wasverzachter", "toiletpapier", "tissues", "afwasmiddel",
    "ariel", "persil", "robijn", "dreft", "page",
    "luiers", "pampers", "huggies",
    "tandpasta", "tandenborstel", "mondwater", "oral-b", "sensodyne", "colgate",
    "deodorant", "douchegel", "scheermesjes", "dove", "axe", "nivea", "gillette",
    "shampoo", "conditioner", "haarverf", "andrelon", "head-shoulders", "loreal",
    "dagcreme", "bodylotion", "zonnebrand", "mascara", "parfum", "vitamines",
    "maandverband", "tampons", "always",
]

def parse_price(s):
    if not s: return None
    s = re.sub(r"[^\d,.]", "", s).replace(",", ".")
    try:
        v = float(s)
        return v if v < 500 else None
    except: return None

def fetch(cat, retries=3):
    url = f"https://www.folderz.nl/aanbiedingen/{cat}"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
            elif r.status_code in [202, 429] or len(r.text) < 500:
                wait = (2 ** attempt) * 5 + random.uniform(1, 3)
                print(f"    [rate limit, wacht {wait:.0f}s]", end="", flush=True)
                time.sleep(wait)
            elif r.status_code == 404:
                return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
    return None

def parse(html):
    products = []
    blocks = re.findall(r"<div class=\"product\">(.*?)</div>\s*</div>\s*</div>\s*</div>", html, re.DOTALL)
    for b in blocks:
        p = {}
        m = re.search(r"product__name[^>]*>([^<]+)", b)
        if m: p["name"] = unescape(m.group(1).strip())
        m = re.search(r"product__price-offer[^>]*>([^<]+)", b)
        if m: p["price"] = parse_price(m.group(1))
        m = re.search(r"product__price-normal[^>]*>([^<]+)", b)
        if m: p["original"] = parse_price(m.group(1))
        m = re.search(r"<img[^>]*alt=\"([^\"]+)\"", b)
        if m: p["store"] = unescape(m.group(1).strip())
        m = re.search(r"badge--secondary\">([^<]+)", b)
        if m:
            pct = re.search(r"(\d+)\s*%", m.group(1))
            if pct: p["badge_pct"] = int(pct.group(1))
        m = re.search(r"product-date[^>]*>([^<]+)", b)
        if m:
            days = re.search(r"(\d+)\s*dag", m.group(1))
            weeks = re.search(r"(\d+)\s*week", m.group(1))
            if days: p["days"] = int(days.group(1))
            elif weeks: p["days"] = int(weeks.group(1)) * 7
        if p.get("name") and p.get("price") and p.get("store") and p["price"] > 0:
            products.append(p)
    return products

def ensure_stores():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    stores = [
        ("kruidvat", "Kruidvat", "💊"), ("etos", "Etos", "💄"),
        ("trekpleister", "Trekpleister", "🏪"), ("da", "DA Drogist", "💊"),
        ("hollandbarrett", "Holland & Barrett", "🌿"), ("douglas", "Douglas", "💐"),
        ("onlinedrogist", "De Online Drogist", "📦"), ("ekoplaza", "Ekoplaza", "🌱"),
        ("makro", "Makro", "🏭"),
    ]
    for code, name, icon in stores:
        cur.execute("INSERT INTO supermarkets (code, name, icon) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET name = %s, icon = %s", (code, name, icon, name, icon))
    conn.commit()
    conn.close()

def sync_db(products):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    today = datetime.now().date()
    inserted = 0
    for p in products:
        store = p.get("store", "").lower()
        code = None
        for pat, c in STORE_MAPPING.items():
            if pat in store:
                code = c
                break
        if not code: continue
        name = p.get("name", "")
        price = p.get("price")
        orig = p.get("original")
        days = p.get("days", 7)
        pct = None
        if orig and orig > price and orig < price * 5:
            pct = round((orig - price) / orig * 100)
        elif p.get("badge_pct"):
            pct = p["badge_pct"]
            if not orig and pct > 0 and pct < 100:
                orig = price / (1 - pct / 100)
        end = today + timedelta(days=days)
        try:
            cur.execute("INSERT INTO promotions (supermarket_code, product_name, original_price, discount_price, discount_percent, promo_type, start_date, end_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (code, name, orig, price, pct, "folder", today, end))
            if cur.rowcount > 0: inserted += 1
        except: pass
    conn.commit()
    conn.close()
    return inserted

def main():
    print("=" * 60)
    print("FOLDERZ SYNC")
    print("=" * 60)
    ensure_stores()
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM promotions WHERE promo_type = 'folder'")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Verwijderd: {deleted} | Categorieen: {len(CATEGORIES)}")
    print()
    
    all_prods = []
    for i, cat in enumerate(CATEGORIES):
        print(f"[{i+1:3}/{len(CATEGORIES)}] {cat:20}", end=" ", flush=True)
        html = fetch(cat)
        if html:
            prods = parse(html)
            print(f"-> {len(prods):3}")
            all_prods.extend(prods)
        else:
            print("-> SKIP")
        time.sleep(2 + random.uniform(0, 1))
        if (i + 1) % 15 == 0:
            print("  ... pauze 8s ...")
            time.sleep(8)
    
    seen = set()
    unique = []
    for p in all_prods:
        key = (p.get("store", "").lower(), p.get("name", "").lower())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    print()
    print(f"Totaal uniek: {len(unique)}")
    inserted = sync_db(unique)
    print(f"Geinserteerd: {inserted}")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT supermarket_code, COUNT(*) FROM promotions WHERE promo_type = 'folder' GROUP BY supermarket_code ORDER BY COUNT(*) DESC LIMIT 10")
    print("\nTop winkels:")
    for r in cur.fetchall():
        print(f"  {r[0]:15} {r[1]:4}")
    cur.execute("SELECT COUNT(*) FROM promotions WHERE promo_type = 'folder'")
    print(f"\nTotaal: {cur.fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    main()
