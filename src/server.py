#!/usr/bin/env python3
"""NL Supermarkt MCP Server - Extended Edition met Prijshistorie, Budget, Winkels & Recepten"""

import os
import asyncio
import json
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'supermarkt_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}

# Drogisterij codes
DROGIST_CODES = ['kruidvat', 'etos', 'trekpleister', 'da', 'hollandbarrett', 'douglas', 'onlinedrogist']

# Category mapping: zoekterm -> lijst van product keywords
CATEGORY_MAPPING = {
    # Drogist categorieën
    'haarverzorging': ['shampoo', 'conditioner', 'haarverf', 'haargel', 'haarspray', 'haar'],
    'mondverzorging': ['tandpasta', 'tandenborstel', 'tandenstokers', 'mondwater', 'floss'],
    'lichaamsverzorging': ['deodorant', 'douchegel', 'bodylotion', 'zeep', 'scheermesjes', 'scheerschuim', 'aftershave'],
    'huidverzorging': ['dagcreme', 'nachtcreme', 'bodylotion', 'zonnebrand', 'aftersun', 'lippenbalsem', 'creme'],
    'make-up': ['mascara', 'eyeliner', 'oogschaduw', 'lippenstift', 'lipgloss', 'foundation', 'nagellak', 'make-up'],
    'parfum': ['parfum', 'eau de toilette', 'geur'],
    'gezondheid': ['vitamines', 'hoestdrank', 'neusspray', 'pleister', 'oogdruppels', 'paracetamol'],
    'oogzorg': ['lenzen', 'contactlenzen', 'oogdruppels', 'lenzenvloeistof'],
    'hygiene': ['maandverband', 'tampons', 'wattenschijfjes', 'tissues'],
    # Supermarkt categorieën
    'vlees': ['gehakt', 'kip', 'rund', 'varken', 'biefstuk', 'worst', 'ham', 'schnitzel', 'spek', 'bacon'],
    'vis': ['zalm', 'kabeljauw', 'tonijn', 'garnalen', 'vis', 'haring', 'makreel'],
    'zuivel': ['melk', 'kaas', 'yoghurt', 'boter', 'kwark', 'vla', 'eieren', 'slagroom'],
    'groenten': ['tomaat', 'komkommer', 'sla', 'paprika', 'ui', 'wortel', 'broccoli', 'aardappel'],
    'fruit': ['appel', 'peer', 'banaan', 'sinaasappel', 'aardbei', 'druiven', 'mango'],
    'dranken': ['cola', 'fanta', 'sap', 'water', 'bier', 'wijn', 'koffie', 'thee'],
}

db_pool = None

def init_pool():
    global db_pool
    if db_pool is None:
        db_pool = pool.ThreadedConnectionPool(1, 10, **DB_CONFIG)
    return db_pool

def get_db():
    p = init_pool()
    conn = p.getconn()
    conn.cursor_factory = RealDictCursor
    return conn

def release_db(conn):
    if db_pool:
        db_pool.putconn(conn)

def haversine(lat1, lon1, lat2, lon2):
    """Bereken afstand tussen twee punten in km"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

server = Server('nl-supermarkt-mcp')

@server.list_tools()
async def list_tools():
    return [
        # Bestaande tools
        Tool(name='zoek_producten', description='Zoek producten op naam bij supermarkten en drogisten.',
             inputSchema={'type': 'object', 'properties': {
                 'query': {'type': 'string'}, 'supermarkt': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 10}
             }, 'required': ['query']}),
        Tool(name='vergelijk_prijzen', description='Vergelijk prijzen bij supermarkten en drogisterijen.',
             inputSchema={'type': 'object', 'properties': {'product': {'type': 'string'}}, 'required': ['product']}),
        Tool(name='optimaliseer_boodschappenlijst', description='Optimaliseer boodschappenlijst voor supermarkten en drogisten.',
             inputSchema={'type': 'object', 'properties': {
                 'producten': {'type': 'array', 'items': {'type': 'string'}},
                 'supermarkten': {'type': 'array', 'items': {'type': 'string'}}
             }, 'required': ['producten']}),
        Tool(name='lijst_supermarkten', description='Toon alle supermarkten en drogisterijen (Kruidvat, Etos, Trekpleister, etc).',
             inputSchema={'type': 'object', 'properties': {}}),
        Tool(name='lijst_drogisten', description='Toon drogisterijen (Kruidvat, Etos, Trekpleister, Holland & Barrett, Douglas) met aanbiedingen voor haarverzorging, huidverzorging, make-up, parfum, gezondheid.',
             inputSchema={'type': 'object', 'properties': {}}),
        Tool(name='bekijk_aanbiedingen', description='Bekijk folder aanbiedingen van supermarkten EN drogisterijen. Categorieën: haarverzorging (shampoo), mondverzorging (tandpasta), lichaamsverzorging (deodorant), huidverzorging (crème), make-up, parfum, gezondheid (vitamines).',
             inputSchema={'type': 'object', 'properties': {
                 'supermarkt': {'type': 'string', 'description': 'Code: ah, jumbo, lidl, kruidvat, etos, trekpleister, hollandbarrett, douglas'},
                 'categorie': {'type': 'string', 'description': 'Categorie: haarverzorging, mondverzorging, lichaamsverzorging, huidverzorging, make-up, parfum, gezondheid, oogzorg'},
                 'limit': {'type': 'integer', 'default': 15}
             }}),
        Tool(name='zoek_recepten', description='Zoek recepten met filters voor dieet.',
             inputSchema={'type': 'object', 'properties': {
                 'query': {'type': 'string'}, 
                 'categorie': {'type': 'string'},
                 'dieet': {'type': 'string', 'description': 'vegetarisch, vegan, glutenvrij'},
                 'max_tijd': {'type': 'integer', 'description': 'Max bereidingstijd in minuten'},
                 'limit': {'type': 'integer', 'default': 10}
             }}),
        Tool(name='plan_boodschappen', 
             description='Plan boodschappen met weekmenu en gedetailleerde boodschappenlijst.',
             inputSchema={'type': 'object', 'properties': {
                 'dagen': {'type': 'integer', 'default': 4},
                 'personen': {'type': 'integer', 'default': 2},
                 'supermarkten': {'type': 'array', 'items': {'type': 'string'}},
                 'voorkeuren': {'type': 'array', 'items': {'type': 'string'}},
                 'dieet': {'type': 'string', 'description': 'vegetarisch, vegan, glutenvrij'},
                 'budget': {'type': 'number', 'description': 'Max budget in EUR'},
                 'basics': {'type': 'boolean', 'default': True}
             }, 'required': ['supermarkten']}),
        
        # === NIEUWE TOOLS ===
        
        # 1. Prijshistorie & Alerts
        Tool(name='prijshistorie', 
             description='Bekijk prijsverloop van een product. Toont laagste prijs ooit, huidige prijs en trend.',
             inputSchema={'type': 'object', 'properties': {
                 'product': {'type': 'string', 'description': 'Productnaam om te zoeken'},
                 'dagen': {'type': 'integer', 'default': 30, 'description': 'Aantal dagen historie'}
             }, 'required': ['product']}),
        Tool(name='prijs_alert', 
             description='Stel een prijsalert in. Krijg melding wanneer product onder bepaalde prijs komt of in aanbieding is.',
             inputSchema={'type': 'object', 'properties': {
                 'product': {'type': 'string'},
                 'max_prijs': {'type': 'number', 'description': 'Max prijs in EUR'},
                 'notify_aanbieding': {'type': 'boolean', 'default': True}
             }, 'required': ['product']}),
        Tool(name='check_alerts', 
             description='Check alle actieve prijsalerts en toon welke producten nu een goede deal zijn.',
             inputSchema={'type': 'object', 'properties': {}}),
        
        # 2. Slimme Boodschappenlijst
        Tool(name='bewaar_boodschappenlijst', 
             description='Bewaar een boodschappenlijst om later te hergebruiken.',
             inputSchema={'type': 'object', 'properties': {
                 'naam': {'type': 'string', 'description': 'Naam voor de lijst (bijv. weekboodschappen, bbq)'},
                 'producten': {'type': 'array', 'items': {'type': 'string'}}
             }, 'required': ['naam', 'producten']}),
        Tool(name='laad_boodschappenlijst', 
             description='Laad een opgeslagen boodschappenlijst en toon huidige prijzen + aanbiedingen.',
             inputSchema={'type': 'object', 'properties': {
                 'naam': {'type': 'string'}
             }, 'required': ['naam']}),
        Tool(name='lijst_boodschappenlijsten', 
             description='Toon alle opgeslagen boodschappenlijsten.',
             inputSchema={'type': 'object', 'properties': {}}),
        Tool(name='wacht_met_kopen', 
             description='Analyseer welke producten binnenkort in aanbieding komen - niet nu kopen!',
             inputSchema={'type': 'object', 'properties': {
                 'producten': {'type': 'array', 'items': {'type': 'string'}}
             }, 'required': ['producten']}),
        
        # 3. Winkel Routeplanner
        Tool(name='vind_winkels', 
             description='Vind dichtstbijzijnde supermarkten op basis van postcode of coordinaten.',
             inputSchema={'type': 'object', 'properties': {
                 'postcode': {'type': 'string'},
                 'latitude': {'type': 'number'},
                 'longitude': {'type': 'number'},
                 'supermarkten': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Filter op specifieke supermarkten'},
                 'max_afstand': {'type': 'number', 'default': 10, 'description': 'Max afstand in km'}
             }}),
        Tool(name='plan_winkelroute', 
             description='Optimaliseer route langs meerdere winkels voor je boodschappenlijst.',
             inputSchema={'type': 'object', 'properties': {
                 'postcode': {'type': 'string'},
                 'producten': {'type': 'array', 'items': {'type': 'string'}},
                 'max_winkels': {'type': 'integer', 'default': 3}
             }, 'required': ['postcode', 'producten']}),
        
        # 4. Budget Tracking
        Tool(name='set_budget', 
             description='Stel een weekbudget in voor boodschappen.',
             inputSchema={'type': 'object', 'properties': {
                 'budget': {'type': 'number', 'description': 'Weekbudget in EUR'}
             }, 'required': ['budget']}),
        Tool(name='budget_check', 
             description='Check of boodschappenlijst binnen budget past. Suggereert goedkopere alternatieven.',
             inputSchema={'type': 'object', 'properties': {
                 'producten': {'type': 'array', 'items': {'type': 'string'}},
                 'budget': {'type': 'number'}
             }, 'required': ['producten', 'budget']}),
        Tool(name='bespaar_tips', 
             description='Krijg persoonlijke bespaartips gebaseerd op je boodschappen.',
             inputSchema={'type': 'object', 'properties': {
                 'producten': {'type': 'array', 'items': {'type': 'string'}}
             }, 'required': ['producten']}),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # === BESTAANDE TOOLS ===
        
        if name == 'zoek_producten':
            query = arguments.get('query', '')
            supermarkt = arguments.get('supermarkt')
            limit = arguments.get('limit', 10)
            if supermarkt:
                cur.execute('SELECT p.*, s.name as supermarket_name, s.icon FROM products p JOIN supermarkets s ON p.supermarket_code = s.code WHERE p.name ILIKE %s AND p.supermarket_code = %s ORDER BY p.price ASC LIMIT %s', (f'%{query}%', supermarkt, limit))
            else:
                cur.execute('SELECT p.*, s.name as supermarket_name, s.icon FROM products p JOIN supermarkets s ON p.supermarket_code = s.code WHERE p.name ILIKE %s ORDER BY p.price ASC LIMIT %s', (f'%{query}%', limit))
            results = cur.fetchall()
            if not results:
                return [TextContent(type='text', text=f'Geen producten gevonden voor "{query}"')]
            lines = [f'Zoekresultaten voor "{query}" ({len(results)} gevonden)\n']
            for r in results:
                lines.append(f'- {r["icon"]} {r["supermarket_name"]}: {r["name"]} - EUR {float(r["price"]):.2f} ({r["unit"]})')
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'vergelijk_prijzen':
            query = arguments.get('product', '')
            cur.execute('SELECT DISTINCT ON (p.supermarket_code) p.*, s.name as supermarket_name, s.icon FROM products p JOIN supermarkets s ON p.supermarket_code = s.code WHERE p.name ILIKE %s ORDER BY p.supermarket_code, p.price ASC', (f'%{query}%',))
            results = cur.fetchall()
            if not results:
                return [TextContent(type='text', text=f'Product "{query}" niet gevonden')]
            results = sorted(results, key=lambda x: float(x['price']))
            lines = [f'Prijsvergelijking: "{query}"\n']
            for r in results:
                marker = ' GOEDKOOPST' if r == results[0] else ''
                lines.append(f'- {r["icon"]} {r["supermarket_name"]}: EUR {float(r["price"]):.2f}{marker}')
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'optimaliseer_boodschappenlijst':
            producten = arguments.get('producten', [])
            supermarkten = arguments.get('supermarkten')
            plan = {}
            total = 0.0
            not_found = []
            for product in producten:
                if supermarkten:
                    cur.execute('SELECT p.*, s.name as sn, s.icon FROM products p JOIN supermarkets s ON p.supermarket_code = s.code WHERE p.name ILIKE %s AND p.supermarket_code = ANY(%s) ORDER BY p.price LIMIT 1', (f'%{product}%', supermarkten))
                else:
                    cur.execute('SELECT p.*, s.name as sn, s.icon FROM products p JOIN supermarkets s ON p.supermarket_code = s.code WHERE p.name ILIKE %s ORDER BY p.price LIMIT 1', (f'%{product}%',))
                r = cur.fetchone()
                if r:
                    sm = r['supermarket_code']
                    if sm not in plan:
                        plan[sm] = {'name': r['sn'], 'icon': r['icon'], 'items': [], 'sub': 0.0}
                    plan[sm]['items'].append({'name': r['name'], 'price': float(r['price'])})
                    plan[sm]['sub'] += float(r['price'])
                    total += float(r['price'])
                else:
                    not_found.append(product)
            lines = [f'BOODSCHAPPENLIJST - Totaal: EUR {total:.2f}\n']
            for sm, p in plan.items():
                lines.append(f'\n{p["icon"]} {p["name"]} (EUR {p["sub"]:.2f}):')
                for i in p['items']:
                    lines.append(f'  [] {i["name"]} - EUR {i["price"]:.2f}')
            if not_found:
                lines.append(f'\nNiet gevonden: {", ".join(not_found)}')
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'lijst_supermarkten':
            cur.execute('SELECT s.*, COUNT(p.id) as cnt FROM supermarkets s LEFT JOIN products p ON s.code = p.supermarket_code GROUP BY s.id ORDER BY s.name')
            supermarkten = []
            drogisten = []
            for r in cur.fetchall():
                line = f'- {r["icon"]} {r["name"]} ({r["code"]}) - {r["cnt"]:,} producten'
                if r["code"] in DROGIST_CODES:
                    drogisten.append(line)
                else:
                    supermarkten.append(line)
            lines = ['SUPERMARKTEN:\n']
            lines.extend(supermarkten)
            if drogisten:
                lines.append('\nDROGISTERIJEN:\n')
                lines.extend(drogisten)
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'lijst_drogisten':
            # Haal drogist info uit supermarkets tabel
            cur.execute('''
                SELECT s.*, COUNT(pr.id) as promo_count
                FROM supermarkets s
                LEFT JOIN promotions pr ON s.code = pr.supermarket_code AND (pr.end_date IS NULL OR pr.end_date >= CURRENT_DATE)
                WHERE s.code = ANY(%s)
                GROUP BY s.id ORDER BY s.name
            ''', (DROGIST_CODES,))
            results = cur.fetchall()

            lines = ['DROGISTERIJEN MET AANBIEDINGEN:\n']
            lines.append('=' * 50)

            for r in results:
                lines.append(f'\n{r["icon"]} {r["name"]} ({r["code"]})')
                lines.append(f'   Aanbiedingen: {r["promo_count"]}')

            # Toon top categorieën
            lines.append('\n\nBESCHIKBARE CATEGORIEËN:')
            lines.append('- haarverzorging (shampoo, conditioner)')
            lines.append('- mondverzorging (tandpasta, tandenborstel)')
            lines.append('- lichaamsverzorging (deodorant, douchegel)')
            lines.append('- huidverzorging (crème, zonnebrand)')
            lines.append('- make-up (mascara, lippenstift)')
            lines.append('- parfum')
            lines.append('- gezondheid (vitamines, pleister)')
            lines.append('- oogzorg (lenzen, oogdruppels)')
            lines.append('\nGebruik bekijk_aanbiedingen met categorie om te zoeken.')

            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'bekijk_aanbiedingen':
            supermarkt = arguments.get('supermarkt')
            categorie = arguments.get('categorie', '')
            limit = arguments.get('limit', 15)
            params, where = [], ["(end_date IS NULL OR end_date >= CURRENT_DATE)"]
            if supermarkt:
                where.append("supermarket_code = %s")
                params.append(supermarkt)
            if categorie:
                # Check of categorie een mapping heeft
                cat_lower = categorie.lower()
                if cat_lower in CATEGORY_MAPPING:
                    # Zoek op alle keywords voor deze categorie
                    keywords = CATEGORY_MAPPING[cat_lower]
                    keyword_clauses = " OR ".join(["product_name ILIKE %s" for _ in keywords])
                    where.append(f"({keyword_clauses})")
                    params.extend([f'%{kw}%' for kw in keywords])
                else:
                    # Zoek letterlijk op de categorie
                    where.append("product_name ILIKE %s")
                    params.append(f'%{categorie}%')
            params.append(limit)
            cur.execute(f'SELECT * FROM promotions WHERE {" AND ".join(where)} ORDER BY discount_percent DESC NULLS LAST LIMIT %s', params)
            results = cur.fetchall()
            if results:
                lines = ['Aanbiedingen:\n']
                for r in results:
                    pct = f' (-{r["discount_percent"]}%)' if r['discount_percent'] else ''
                    promo = f' [{r["promo_type"]}]' if r['promo_type'] else ''
                    lines.append(f'- {r["supermarket_code"].upper()}: {r["product_name"]} EUR {float(r["discount_price"]):.2f}{pct}{promo}')
                return [TextContent(type='text', text='\n'.join(lines))]
            return [TextContent(type='text', text='Geen aanbiedingen')]

        elif name == 'zoek_recepten':
            query = arguments.get('query', '')
            categorie = arguments.get('categorie')
            dieet = arguments.get('dieet')
            max_tijd = arguments.get('max_tijd')
            limit = arguments.get('limit', 10)
            
            params, where = [], []
            if query:
                where.append("(naam ILIKE %s OR ingredienten::text ILIKE %s OR tags::text ILIKE %s)")
                params.extend([f'%{query}%'] * 3)
            if categorie:
                where.append("categorie = %s")
                params.append(categorie)
            if dieet:
                where.append("tags::text ILIKE %s")
                params.append(f'%{dieet}%')
            if max_tijd:
                where.append("bereidingstijd <= %s")
                params.append(max_tijd)
            
            wc = f"WHERE {' AND '.join(where)}" if where else ""
            params.append(limit)
            cur.execute(f'SELECT * FROM recepten {wc} ORDER BY CASE WHEN bron = \'eigen\' THEN 0 ELSE 1 END LIMIT %s', params)
            results = cur.fetchall()
            if not results:
                return [TextContent(type='text', text='Geen recepten gevonden')]
            lines = ['Recepten:\n']
            for r in results:
                tags = ', '.join(r.get('tags', [])[:3]) if r.get('tags') else ''
                tag_str = f' [{tags}]' if tags else ''
                lines.append(f'\n{r["naam"]} ({r["bereidingstijd"]} min, {r["porties"]} pers){tag_str}')
                lines.append(f'  Ingredienten: {", ".join([i["naam"] for i in r["ingredienten"][:6]])}')
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'plan_boodschappen':
            dagen = arguments.get('dagen', 4)
            personen = arguments.get('personen', 2)
            supermarkten = arguments.get('supermarkten', [])
            voorkeuren = arguments.get('voorkeuren', ['pasta', 'rijst', 'hollands'])
            dieet = arguments.get('dieet')
            budget = arguments.get('budget')
            basics = arguments.get('basics', True)

            sm_ph = ','.join(['%s'] * len(supermarkten))
            cur.execute(f'''
                SELECT supermarket_code, product_name, discount_price, discount_percent, promo_type
                FROM promotions WHERE supermarket_code IN ({sm_ph})
                AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                ORDER BY discount_percent DESC NULLS LAST
            ''', supermarkten)
            aanbiedingen = cur.fetchall()

            # Query recepten met dieet filter
            query_parts = []
            params = []
            if voorkeuren:
                voorkeur_clause = " OR ".join(["categorie = %s" for _ in voorkeuren])
                query_parts.append(f'({voorkeur_clause})')
                params.extend(voorkeuren)
            if dieet:
                query_parts.append("tags::text ILIKE %s")
                params.append(f'%{dieet}%')
            
            where_clause = f"WHERE {' AND '.join(query_parts)}" if query_parts else ""
            cur.execute(f'SELECT * FROM recepten {where_clause} ORDER BY CASE WHEN bron = \'eigen\' THEN 0 ELSE 1 END, RANDOM()', params)
            recepten = cur.fetchall()

            def score(recept):
                s = 0
                matches = []
                for a in aanbiedingen:
                    for ing in recept['ingredienten']:
                        if any(w in a['product_name'].lower() for w in ing['naam'].lower().split()):
                            s += (a['discount_percent'] or 5)
                            matches.append((ing['naam'], a))
                            break
                return s, matches

            scored = [(r, *score(r)) for r in recepten]
            scored.sort(key=lambda x: x[1], reverse=True)
            gekozen = scored[:dagen]

            boodschappen = {}
            output = []
            output.append('=' * 60)
            output.append(f'WEEKPLAN: {dagen} dagen, {personen} personen')
            if dieet:
                output.append(f'Dieet: {dieet}')
            if budget:
                output.append(f'Budget: EUR {budget:.2f}')
            output.append('=' * 60)

            for dag, (recept, score_val, matches) in enumerate(gekozen, 1):
                output.append(f'\n--- DAG {dag}: {recept["naam"]} ({recept["bereidingstijd"]} min) ---')
                output.append('\nINGREDIENTEN:')
                for ing in recept['ingredienten']:
                    output.append(f'  - {ing["hoeveelheid"]} {ing["naam"]}')
                    cur.execute('SELECT name, price, supermarket_code FROM products WHERE name ILIKE %s AND supermarket_code = ANY(%s) ORDER BY price LIMIT 1', 
                                (f'%{ing["naam"]}%', supermarkten))
                    prod = cur.fetchone()
                    if prod and prod['name'] not in boodschappen:
                        boodschappen[prod['name']] = (float(prod['price']), prod['supermarket_code'], None, False)
                
                output.append('\nBEREIDING:')
                for i, stap in enumerate(recept['instructies'][:5], 1):
                    output.append(f'  {i}. {stap}')
                
                if matches:
                    output.append('\nAANBIEDINGEN VOOR DIT RECEPT:')
                    seen = set()
                    for ing_naam, a in matches[:3]:
                        if a['product_name'] not in seen:
                            seen.add(a['product_name'])
                            pct = f" -{a['discount_percent']}%" if a['discount_percent'] else ''
                            pt = f" [{a['promo_type']}]" if a['promo_type'] else ''
                            output.append(f'  * {a["supermarket_code"].upper()}: {a["product_name"]} EUR {float(a["discount_price"]):.2f}{pct}{pt}')
                            boodschappen[a['product_name']] = (float(a['discount_price']), a['supermarket_code'], a['promo_type'], True)

            if basics:
                output.append('\n' + '=' * 60)
                output.append('BASISPRODUCTEN')
                output.append('=' * 60)
                for item in ['halfvolle melk', 'wit brood', 'eieren', 'roomboter', 'goudse kaas']:
                    cur.execute('SELECT name, price, supermarket_code FROM products WHERE name ILIKE %s AND supermarket_code = ANY(%s) ORDER BY price LIMIT 1', 
                                (f'%{item}%', supermarkten))
                    r = cur.fetchone()
                    if r:
                        output.append(f'  - {r["name"]} EUR {float(r["price"]):.2f} ({r["supermarket_code"].upper()})')
                        if r['name'] not in boodschappen:
                            boodschappen[r['name']] = (float(r['price']), r['supermarket_code'], None, False)

            output.append('\n' + '=' * 60)
            output.append('BOODSCHAPPENLIJST PER SUPERMARKT')
            output.append('=' * 60)

            per_winkel = {}
            totaal = 0
            for product, (prijs, winkel, promo, is_aanbieding) in boodschappen.items():
                if winkel not in per_winkel:
                    per_winkel[winkel] = []
                per_winkel[winkel].append((product, prijs, promo, is_aanbieding))
                totaal += prijs

            for winkel in sorted(per_winkel.keys()):
                items = per_winkel[winkel]
                subtot = sum(p for _, p, _, _ in items)
                output.append(f'\n### {winkel.upper()} - Subtotaal: EUR {subtot:.2f} ###')
                for product, prijs, promo, is_aanbieding in sorted(items, key=lambda x: x[0]):
                    aanbieding_marker = ' [AANBIEDING]' if is_aanbieding else ''
                    promo_txt = f' ({promo})' if promo else ''
                    output.append(f'  [ ] {product}')
                    output.append(f'      EUR {prijs:.2f}{promo_txt}{aanbieding_marker}')

            output.append(f'\n{"=" * 60}')
            output.append(f'TOTAAL GESCHAT: EUR {totaal:.2f}')
            
            if budget:
                if totaal <= budget:
                    output.append(f'BINNEN BUDGET! Je houdt EUR {budget - totaal:.2f} over')
                else:
                    output.append(f'LET OP: EUR {totaal - budget:.2f} BOVEN BUDGET!')
            
            output.append('=' * 60)

            return [TextContent(type='text', text='\n'.join(output))]

        # === NIEUWE TOOLS ===

        # 1. PRIJSHISTORIE & ALERTS
        elif name == 'prijshistorie':
            product = arguments.get('product', '')
            dagen = arguments.get('dagen', 30)
            
            # Zoek product
            cur.execute('''
                SELECT p.id, p.name, p.price, p.supermarket_code, s.name as sm_name
                FROM products p
                JOIN supermarkets s ON p.supermarket_code = s.code
                WHERE p.name ILIKE %s
                ORDER BY p.price ASC
                LIMIT 5
            ''', (f'%{product}%',))
            products = cur.fetchall()
            
            if not products:
                return [TextContent(type='text', text=f'Product "{product}" niet gevonden')]
            
            lines = [f'PRIJSHISTORIE: "{product}"\n']
            lines.append('=' * 50)
            
            for p in products:
                # Haal prijshistorie op
                cur.execute('''
                    SELECT price, recorded_at 
                    FROM price_history 
                    WHERE product_id = %s 
                    AND recorded_at > NOW() - INTERVAL '%s days'
                    ORDER BY recorded_at DESC
                ''', (p['id'], dagen))
                history = cur.fetchall()
                
                huidige_prijs = float(p['price'])
                laagste_prijs = huidige_prijs
                hoogste_prijs = huidige_prijs
                
                if history:
                    prijzen = [float(h['price']) for h in history]
                    laagste_prijs = min(prijzen + [huidige_prijs])
                    hoogste_prijs = max(prijzen + [huidige_prijs])
                
                # Check aanbiedingen
                cur.execute('''
                    SELECT discount_price, discount_percent, promo_type
                    FROM promotions
                    WHERE product_name ILIKE %s
                    AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                    ORDER BY discount_percent DESC NULLS LAST
                    LIMIT 1
                ''', (f'%{p["name"]}%',))
                promo = cur.fetchone()
                
                lines.append(f'\n{p["sm_name"]}: {p["name"]}')
                lines.append(f'  Huidige prijs: EUR {huidige_prijs:.2f}')
                lines.append(f'  Laagste ooit:  EUR {laagste_prijs:.2f}')
                lines.append(f'  Hoogste ooit:  EUR {hoogste_prijs:.2f}')
                
                if huidige_prijs == laagste_prijs:
                    lines.append('  >>> LAAGSTE PRIJS OOIT! <<<')
                elif huidige_prijs <= laagste_prijs * 1.1:
                    lines.append('  -> Bijna laagste prijs!')
                
                if promo:
                    pct = f" (-{promo['discount_percent']}%)" if promo['discount_percent'] else ''
                    pt = f" [{promo['promo_type']}]" if promo['promo_type'] else ''
                    lines.append(f'  IN AANBIEDING: EUR {float(promo["discount_price"]):.2f}{pct}{pt}')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'prijs_alert':
            product = arguments.get('product', '')
            max_prijs = arguments.get('max_prijs')
            notify_aanbieding = arguments.get('notify_aanbieding', True)
            
            cur.execute('''
                INSERT INTO product_alerts (product_query, max_prijs, notify_on_sale)
                VALUES (%s, %s, %s)
                RETURNING id
            ''', (product, max_prijs, notify_aanbieding))
            conn.commit()
            alert_id = cur.fetchone()['id']
            
            lines = ['PRIJSALERT INGESTELD\n']
            lines.append(f'Product: {product}')
            if max_prijs:
                lines.append(f'Melding bij prijs onder: EUR {max_prijs:.2f}')
            if notify_aanbieding:
                lines.append('Melding bij aanbiedingen: Ja')
            lines.append(f'\nAlert ID: {alert_id}')
            lines.append('\nGebruik "check_alerts" om te zien welke producten nu een goede deal zijn.')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'check_alerts':
            cur.execute('SELECT * FROM product_alerts ORDER BY created_at DESC')
            alerts = cur.fetchall()
            
            if not alerts:
                return [TextContent(type='text', text='Geen prijsalerts ingesteld. Gebruik "prijs_alert" om er een toe te voegen.')]
            
            lines = ['PRIJSALERTS CHECK\n']
            lines.append('=' * 50)
            goede_deals = []
            
            for alert in alerts:
                query = alert['product_query']
                max_prijs = float(alert['max_prijs']) if alert['max_prijs'] else None
                
                # Check huidige prijs
                cur.execute('''
                    SELECT name, price, supermarket_code FROM products
                    WHERE name ILIKE %s ORDER BY price LIMIT 1
                ''', (f'%{query}%',))
                product = cur.fetchone()
                
                # Check aanbiedingen
                cur.execute('''
                    SELECT product_name, discount_price, discount_percent, promo_type, supermarket_code
                    FROM promotions
                    WHERE product_name ILIKE %s
                    AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                    ORDER BY discount_price LIMIT 1
                ''', (f'%{query}%',))
                promo = cur.fetchone()
                
                is_deal = False
                if product:
                    prijs = float(product['price'])
                    if max_prijs and prijs <= max_prijs:
                        is_deal = True
                        goede_deals.append(f'  {product["name"]} - EUR {prijs:.2f} (onder max van EUR {max_prijs:.2f})')
                
                if promo and alert['notify_on_sale']:
                    is_deal = True
                    pct = f" -{promo['discount_percent']}%" if promo['discount_percent'] else ''
                    goede_deals.append(f'  {promo["product_name"]} - EUR {float(promo["discount_price"]):.2f}{pct} [{promo["supermarket_code"].upper()}]')
            
            if goede_deals:
                lines.append('\nGOEDE DEALS NU:')
                lines.extend(goede_deals)
            else:
                lines.append('\nGeen van je alerts heeft momenteel een goede deal.')
            
            lines.append(f'\n\nTotaal actieve alerts: {len(alerts)}')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        # 2. SLIMME BOODSCHAPPENLIJST
        elif name == 'bewaar_boodschappenlijst':
            naam = arguments.get('naam', '')
            producten = arguments.get('producten', [])
            
            # Bereken totaal
            totaal = 0.0
            items = []
            for p in producten:
                cur.execute('SELECT name, price FROM products WHERE name ILIKE %s ORDER BY price LIMIT 1', (f'%{p}%',))
                r = cur.fetchone()
                if r:
                    items.append({'query': p, 'name': r['name'], 'price': float(r['price'])})
                    totaal += float(r['price'])
                else:
                    items.append({'query': p, 'name': p, 'price': None})
            
            cur.execute('''
                INSERT INTO shopping_lists (naam, items, totaal)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
            ''', (naam, json.dumps(items), totaal))
            conn.commit()
            
            lines = [f'BOODSCHAPPENLIJST OPGESLAGEN\n']
            lines.append(f'Naam: {naam}')
            lines.append(f'Aantal items: {len(items)}')
            lines.append(f'Geschat totaal: EUR {totaal:.2f}')
            lines.append('\nGebruik "laad_boodschappenlijst" om deze later te laden.')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'laad_boodschappenlijst':
            naam = arguments.get('naam', '')
            
            cur.execute('SELECT * FROM shopping_lists WHERE naam ILIKE %s ORDER BY updated_at DESC LIMIT 1', (f'%{naam}%',))
            lijst = cur.fetchone()
            
            if not lijst:
                return [TextContent(type='text', text=f'Boodschappenlijst "{naam}" niet gevonden')]
            
            items = lijst['items'] if isinstance(lijst['items'], list) else json.loads(lijst['items'])
            
            lines = [f'BOODSCHAPPENLIJST: {lijst["naam"]}\n']
            lines.append('=' * 50)
            
            totaal = 0.0
            besparingen = 0.0
            
            for item in items:
                query = item.get('query', item.get('name', ''))
                
                # Zoek huidige prijs
                cur.execute('SELECT name, price, supermarket_code FROM products WHERE name ILIKE %s ORDER BY price LIMIT 1', (f'%{query}%',))
                product = cur.fetchone()
                
                # Zoek aanbieding
                cur.execute('''
                    SELECT product_name, discount_price, discount_percent, promo_type, supermarket_code
                    FROM promotions WHERE product_name ILIKE %s
                    AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                    ORDER BY discount_price LIMIT 1
                ''', (f'%{query}%',))
                promo = cur.fetchone()
                
                if promo:
                    prijs = float(promo['discount_price'])
                    pct = f" (-{promo['discount_percent']}%)" if promo['discount_percent'] else ''
                    lines.append(f'  {promo["product_name"]}')
                    lines.append(f'    EUR {prijs:.2f}{pct} AANBIEDING! [{promo["supermarket_code"].upper()}]')
                    if product:
                        besparingen += float(product['price']) - prijs
                    totaal += prijs
                elif product:
                    prijs = float(product['price'])
                    lines.append(f'  {product["name"]}')
                    lines.append(f'    EUR {prijs:.2f} [{product["supermarket_code"].upper()}]')
                    totaal += prijs
                else:
                    lines.append(f'  {query} - niet gevonden')
            
            lines.append('\n' + '=' * 50)
            lines.append(f'TOTAAL: EUR {totaal:.2f}')
            if besparingen > 0:
                lines.append(f'BESPAARD door aanbiedingen: EUR {besparingen:.2f}')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'lijst_boodschappenlijsten':
            cur.execute('SELECT naam, totaal, created_at, json_array_length(items::json) as item_count FROM shopping_lists ORDER BY updated_at DESC')
            lijsten = cur.fetchall()
            
            if not lijsten:
                return [TextContent(type='text', text='Geen opgeslagen boodschappenlijsten. Gebruik "bewaar_boodschappenlijst" om er een te maken.')]
            
            lines = ['OPGESLAGEN BOODSCHAPPENLIJSTEN\n']
            for l in lijsten:
                datum = l['created_at'].strftime('%d-%m-%Y') if l['created_at'] else ''
                lines.append(f'- {l["naam"]} ({l["item_count"]} items, EUR {float(l["totaal"] or 0):.2f}) - {datum}')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'wacht_met_kopen':
            producten = arguments.get('producten', [])
            
            lines = ['KOOP-ADVIES: Nu kopen of wachten?\n']
            lines.append('=' * 50)
            
            nu_kopen = []
            wachten = []
            
            for p in producten:
                # Check huidige aanbiedingen
                cur.execute('''
                    SELECT product_name, discount_price, discount_percent, promo_type, end_date
                    FROM promotions WHERE product_name ILIKE %s
                    AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                    ORDER BY discount_percent DESC NULLS LAST LIMIT 1
                ''', (f'%{p}%',))
                promo = cur.fetchone()
                
                # Check of dit product regelmatig in aanbieding is
                cur.execute('''
                    SELECT COUNT(*) as cnt FROM promotions
                    WHERE product_name ILIKE %s
                ''', (f'%{p}%',))
                promo_count = cur.fetchone()['cnt']
                
                if promo:
                    pct = promo['discount_percent'] or 0
                    end = promo['end_date'].strftime('%d-%m') if promo['end_date'] else 'onbekend'
                    nu_kopen.append(f'  {p}: NU IN AANBIEDING (-{pct}%) - geldig t/m {end}')
                elif promo_count > 2:
                    wachten.append(f'  {p}: komt regelmatig in aanbieding - WACHT')
                else:
                    nu_kopen.append(f'  {p}: geen aanbieding verwacht - gewoon kopen')
            
            if nu_kopen:
                lines.append('\nNU KOPEN:')
                lines.extend(nu_kopen)
            
            if wachten:
                lines.append('\nWACHTEN MET KOPEN:')
                lines.extend(wachten)
            
            return [TextContent(type='text', text='\n'.join(lines))]

        # 3. WINKEL ROUTEPLANNER
        elif name == 'vind_winkels':
            postcode = arguments.get('postcode')
            lat = arguments.get('latitude')
            lon = arguments.get('longitude')
            filter_sm = arguments.get('supermarkten')
            max_afstand = arguments.get('max_afstand', 10)
            
            # Als we geen coordinaten hebben, gebruik een standaard (Amsterdam)
            if not lat or not lon:
                # In productie zou je hier een geocoding API gebruiken
                lat, lon = 52.3676, 4.9041  # Amsterdam centrum
            
            cur.execute('SELECT * FROM supermarket_locations')
            locaties = cur.fetchall()
            
            if not locaties:
                # Geen locaties in database, geef algemeen advies
                lines = ['DICHTSTBIJZIJNDE WINKELS\n']
                lines.append('Winkellocaties nog niet geladen.')
                lines.append('\nTip: Gebruik Google Maps om winkels bij jou in de buurt te vinden.')
                lines.append('\nBeschikbare supermarkten:')
                
                cur.execute('SELECT code, name, icon FROM supermarkets ORDER BY name')
                for s in cur.fetchall():
                    lines.append(f'  {s["icon"]} {s["name"]}')
                
                return [TextContent(type='text', text='\n'.join(lines))]
            
            # Bereken afstanden
            winkels_met_afstand = []
            for loc in locaties:
                if filter_sm and loc['supermarket_code'] not in filter_sm:
                    continue
                if loc['latitude'] and loc['longitude']:
                    afstand = haversine(lat, lon, float(loc['latitude']), float(loc['longitude']))
                    if afstand <= max_afstand:
                        winkels_met_afstand.append((loc, afstand))
            
            winkels_met_afstand.sort(key=lambda x: x[1])
            
            lines = [f'WINKELS BINNEN {max_afstand} KM\n']
            for loc, afstand in winkels_met_afstand[:10]:
                lines.append(f'  {loc["naam"]} ({afstand:.1f} km)')
                lines.append(f'    {loc["adres"]}, {loc["postcode"]} {loc["stad"]}')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'plan_winkelroute':
            postcode = arguments.get('postcode', '')
            producten = arguments.get('producten', [])
            max_winkels = arguments.get('max_winkels', 3)
            
            # Bepaal goedkoopste winkel per product
            winkel_producten = {}
            for p in producten:
                cur.execute('''
                    SELECT name, price, supermarket_code 
                    FROM products WHERE name ILIKE %s 
                    ORDER BY price LIMIT 1
                ''', (f'%{p}%',))
                r = cur.fetchone()
                if r:
                    sm = r['supermarket_code']
                    if sm not in winkel_producten:
                        winkel_producten[sm] = []
                    winkel_producten[sm].append({'name': r['name'], 'price': float(r['price'])})
            
            # Sorteer winkels op aantal producten
            gesorteerd = sorted(winkel_producten.items(), key=lambda x: len(x[1]), reverse=True)
            
            lines = ['OPTIMALE WINKELROUTE\n']
            lines.append(f'Startpunt: {postcode}')
            lines.append('=' * 50)
            
            totaal = 0
            for i, (winkel, items) in enumerate(gesorteerd[:max_winkels], 1):
                subtotaal = sum(item['price'] for item in items)
                totaal += subtotaal
                
                cur.execute('SELECT name, icon FROM supermarkets WHERE code = %s', (winkel,))
                sm = cur.fetchone()
                
                lines.append(f'\nSTOP {i}: {sm["icon"]} {sm["name"]}')
                lines.append(f'  Producten: {len(items)} | Subtotaal: EUR {subtotaal:.2f}')
                for item in items:
                    lines.append(f'    - {item["name"]} EUR {item["price"]:.2f}')
            
            lines.append('\n' + '=' * 50)
            lines.append(f'TOTAAL: EUR {totaal:.2f}')
            lines.append(f'Aantal winkels: {min(len(gesorteerd), max_winkels)}')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        # 4. BUDGET TRACKING
        elif name == 'set_budget':
            budget = arguments.get('budget', 0)
            week = datetime.now().isocalendar()[1]
            jaar = datetime.now().year
            
            cur.execute('''
                INSERT INTO budget_history (weeknummer, jaar, budget, uitgegeven, bespaard)
                VALUES (%s, %s, %s, 0, 0)
                ON CONFLICT DO NOTHING
            ''', (week, jaar, budget))
            conn.commit()
            
            lines = ['WEEKBUDGET INGESTELD\n']
            lines.append(f'Week {week} van {jaar}')
            lines.append(f'Budget: EUR {budget:.2f}')
            lines.append('\nGebruik "budget_check" om te zien of je boodschappen binnen budget passen.')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'budget_check':
            producten = arguments.get('producten', [])
            budget = arguments.get('budget', 0)
            
            totaal = 0
            items = []
            
            for p in producten:
                cur.execute('SELECT name, price, supermarket_code FROM products WHERE name ILIKE %s ORDER BY price LIMIT 1', (f'%{p}%',))
                r = cur.fetchone()
                if r:
                    items.append({'query': p, 'name': r['name'], 'price': float(r['price']), 'sm': r['supermarket_code']})
                    totaal += float(r['price'])
            
            lines = ['BUDGET CHECK\n']
            lines.append('=' * 50)
            lines.append(f'Budget: EUR {budget:.2f}')
            lines.append(f'Totaal boodschappen: EUR {totaal:.2f}')
            
            if totaal <= budget:
                over = budget - totaal
                lines.append(f'\nBINNEN BUDGET! EUR {over:.2f} over')
            else:
                tekort = totaal - budget
                lines.append(f'\nBOVEN BUDGET! EUR {tekort:.2f} te veel')
                lines.append('\nGOEDKOPERE ALTERNATIEVEN:')
                
                # Zoek alternatieven voor duurste items
                items_sorted = sorted(items, key=lambda x: x['price'], reverse=True)
                for item in items_sorted[:3]:
                    cur.execute('''
                        SELECT name, price, supermarket_code 
                        FROM products 
                        WHERE name ILIKE %s AND price < %s
                        ORDER BY price LIMIT 1
                    ''', (f'%{item["query"]}%', item['price'] * 0.8))
                    alt = cur.fetchone()
                    if alt:
                        besparing = item['price'] - float(alt['price'])
                        lines.append(f'  {item["name"]} EUR {item["price"]:.2f}')
                        lines.append(f'    -> {alt["name"]} EUR {float(alt["price"]):.2f} (bespaar EUR {besparing:.2f})')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'bespaar_tips':
            producten = arguments.get('producten', [])
            
            lines = ['PERSOONLIJKE BESPAARTIPS\n']
            lines.append('=' * 50)
            
            totale_besparing = 0
            tips = []
            
            for p in producten:
                # Check aanbieding
                cur.execute('''
                    SELECT product_name, discount_price, discount_percent, promo_type, supermarket_code
                    FROM promotions WHERE product_name ILIKE %s
                    AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                    ORDER BY discount_percent DESC NULLS LAST LIMIT 1
                ''', (f'%{p}%',))
                promo = cur.fetchone()
                
                # Check goedkoopste variant
                cur.execute('''
                    SELECT name, price, supermarket_code FROM products
                    WHERE name ILIKE %s ORDER BY price LIMIT 1
                ''', (f'%{p}%',))
                goedkoopst = cur.fetchone()
                
                # Check huismerk alternatief
                cur.execute('''
                    SELECT name, price, supermarket_code FROM products
                    WHERE name ILIKE %s 
                    AND (name ILIKE '%%huismerk%%' OR name ILIKE '%%basic%%' OR name ILIKE '%%1 de beste%%')
                    ORDER BY price LIMIT 1
                ''', (f'%{p}%',))
                huismerk = cur.fetchone()
                
                if promo:
                    pct = promo['discount_percent'] or 0
                    tips.append(f'AANBIEDING: {promo["product_name"]}')
                    tips.append(f'  -{pct}% bij {promo["supermarket_code"].upper()} - EUR {float(promo["discount_price"]):.2f}')
                    if goedkoopst:
                        totale_besparing += float(goedkoopst['price']) - float(promo['discount_price'])
                
                if huismerk and goedkoopst and float(huismerk['price']) < float(goedkoopst['price']) * 0.8:
                    besparing = float(goedkoopst['price']) - float(huismerk['price'])
                    tips.append(f'HUISMERK TIP: {huismerk["name"]}')
                    tips.append(f'  EUR {float(huismerk["price"]):.2f} (bespaar EUR {besparing:.2f})')
                    totale_besparing += besparing
            
            if tips:
                lines.extend(tips)
            else:
                lines.append('Geen specifieke tips gevonden voor deze producten.')
            
            lines.append('\n' + '=' * 50)
            lines.append(f'POTENTIELE BESPARING: EUR {totale_besparing:.2f}')
            
            # Algemene tips
            lines.append('\nALGEMENE TIPS:')
            lines.append('- Koop huismerken i.p.v. A-merken')
            lines.append('- Let op kilo/literprijs')
            lines.append('- Gebruik "wacht_met_kopen" voor timing')
            lines.append('- Combineer winkels voor beste deals')
            
            return [TextContent(type='text', text='\n'.join(lines))]

        return [TextContent(type='text', text=f'Onbekende tool: {name}')]

    except Exception as e:
        import traceback
        return [TextContent(type='text', text=f'Fout: {str(e)}\n{traceback.format_exc()}')]
    finally:
        if conn:
            release_db(conn)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
