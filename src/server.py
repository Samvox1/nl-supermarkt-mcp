#!/usr/bin/env python3
"""NL Supermarkt MCP Server - Docker compatible"""

import os
import asyncio
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Database config from environment variables
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'supermarkt_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
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

server = Server('nl-supermarkt-mcp')

@server.list_tools()
async def list_tools():
    return [
        Tool(name='zoek_producten', description='Zoek producten op naam.',
             inputSchema={'type': 'object', 'properties': {
                 'query': {'type': 'string'}, 'supermarkt': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 10}
             }, 'required': ['query']}),
        Tool(name='vergelijk_prijzen', description='Vergelijk prijzen bij supermarkten.',
             inputSchema={'type': 'object', 'properties': {'product': {'type': 'string'}}, 'required': ['product']}),
        Tool(name='optimaliseer_boodschappenlijst', description='Optimaliseer boodschappenlijst.',
             inputSchema={'type': 'object', 'properties': {
                 'producten': {'type': 'array', 'items': {'type': 'string'}},
                 'supermarkten': {'type': 'array', 'items': {'type': 'string'}}
             }, 'required': ['producten']}),
        Tool(name='lijst_supermarkten', description='Toon supermarkten.',
             inputSchema={'type': 'object', 'properties': {}}),
        Tool(name='bekijk_aanbiedingen', description='Bekijk folder aanbiedingen.',
             inputSchema={'type': 'object', 'properties': {
                 'supermarkt': {'type': 'string'}, 'categorie': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 15}
             }}),
        Tool(name='zoek_recepten', description='Zoek recepten.',
             inputSchema={'type': 'object', 'properties': {
                 'query': {'type': 'string'}, 'categorie': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 10}
             }}),
        Tool(name='plan_boodschappen', 
             description='Plan boodschappen: geeft weekmenu met COMPLETE recepten en GEDETAILLEERDE boodschappenlijst per winkel.',
             inputSchema={'type': 'object', 'properties': {
                 'dagen': {'type': 'integer', 'default': 4},
                 'personen': {'type': 'integer', 'default': 2},
                 'supermarkten': {'type': 'array', 'items': {'type': 'string'}},
                 'voorkeuren': {'type': 'array', 'items': {'type': 'string'}},
                 'basics': {'type': 'boolean', 'default': True}
             }, 'required': ['supermarkten']})
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

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
            lines = ['Supermarkten:\n']
            for r in cur.fetchall():
                lines.append(f'- {r["icon"]} {r["name"]} ({r["code"]}) - {r["cnt"]:,} producten')
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
            limit = arguments.get('limit', 10)
            params, where = [], []
            if query:
                where.append("(naam ILIKE %s OR ingredienten::text ILIKE %s OR tags::text ILIKE %s)")
                params.extend([f'%{query}%'] * 3)
            if categorie:
                where.append("categorie = %s")
                params.append(categorie)
            wc = f"WHERE {' AND '.join(where)}" if where else ""
            params.append(limit)
            cur.execute(f'SELECT * FROM recepten {wc} ORDER BY CASE WHEN bron = \'eigen\' THEN 0 ELSE 1 END LIMIT %s', params)
            results = cur.fetchall()
            if not results:
                return [TextContent(type='text', text='Geen recepten gevonden')]
            lines = ['Recepten:\n']
            for r in results:
                lines.append(f'\n{r["naam"]} ({r["bereidingstijd"]} min, {r["porties"]} pers)')
                lines.append(f'  Ingredienten: {", ".join([i["naam"] for i in r["ingredienten"][:6]])}')
            return [TextContent(type='text', text='\n'.join(lines))]

        elif name == 'plan_boodschappen':
            dagen = arguments.get('dagen', 4)
            personen = arguments.get('personen', 2)
            supermarkten = arguments.get('supermarkten', [])
            voorkeuren = arguments.get('voorkeuren', ['pasta', 'rijst', 'hollands'])
            basics = arguments.get('basics', True)

            sm_ph = ','.join(['%s'] * len(supermarkten))
            cur.execute(f'''
                SELECT supermarket_code, product_name, discount_price, discount_percent, promo_type
                FROM promotions WHERE supermarket_code IN ({sm_ph})
                AND (end_date IS NULL OR end_date >= CURRENT_DATE)
                ORDER BY discount_percent DESC NULLS LAST
            ''', supermarkten)
            aanbiedingen = cur.fetchall()

            if voorkeuren:
                voorkeur_clause = " OR ".join(["categorie = %s" for _ in voorkeuren])
                cur.execute(f'SELECT * FROM recepten WHERE {voorkeur_clause} ORDER BY CASE WHEN bron = \'eigen\' THEN 0 ELSE 1 END, RANDOM()', voorkeuren)
            else:
                cur.execute('SELECT * FROM recepten ORDER BY RANDOM()')
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
                            output.append(f'  * {a["supermarket_code"].upper()}: {a["product_name"][:35]} EUR {float(a["discount_price"]):.2f}{pct}{pt}')
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
                        output.append(f'  - {r["name"][:40]} EUR {float(r["price"]):.2f} ({r["supermarket_code"].upper()})')
                        if r['name'] not in boodschappen:
                            boodschappen[r['name']] = (float(r['price']), r['supermarket_code'], None, False)

            output.append('\n' + '=' * 60)
            output.append('BOODSCHAPPENLIJST PER SUPERMARKT')
            output.append('=' * 60)
            output.append('(Neem dit mee naar de winkel!)\n')

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
                    output.append(f'  [ ] {product[:45]}')
                    output.append(f'      EUR {prijs:.2f}{promo_txt}{aanbieding_marker}')

            output.append(f'\n{"=" * 60}')
            output.append(f'TOTAAL GESCHAT: EUR {totaal:.2f}')
            output.append('=' * 60)
            output.append('\nLET OP:')
            output.append('- "1+1 gratis" = je moet 2 kopen')  
            output.append('- "2e halve prijs" = koop 2, betaal 1.5x de prijs')

            return [TextContent(type='text', text='\n'.join(output))]

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
