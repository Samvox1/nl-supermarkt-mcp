#!/usr/bin/env python3
"""
Sync recepten van meerdere APIs naar de database.
Maakt eerst de tabel leeg voor verse data.
"""
import requests
import psycopg2
from psycopg2.extras import Json
import time

import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'supermarkt_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}
MEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"

DUTCH_RECIPES = [
    {'naam': 'Spaghetti Bolognese', 'categorie': 'pasta', 'bereidingstijd': 30, 'porties': 4,
     'ingredienten': [{'naam': 'spaghetti', 'hoeveelheid': '400g'}, {'naam': 'rundergehakt', 'hoeveelheid': '500g'}, 
                      {'naam': 'passata', 'hoeveelheid': '400ml'}, {'naam': 'ui', 'hoeveelheid': '1'}, 
                      {'naam': 'knoflook', 'hoeveelheid': '2 tenen'}, {'naam': 'wortel', 'hoeveelheid': '1'}, 
                      {'naam': 'parmezaanse kaas', 'hoeveelheid': '50g'}],
     'instructies': ['Snipper ui en knoflook, rasp wortel.', 'Bak gehakt rul in olijfolie.', 
                     'Voeg ui, knoflook, wortel toe, bak 5 min.', 'Voeg passata toe, 20 min sudderen.', 
                     'Kook spaghetti, serveer met saus en parmezaan.'],
     'tags': ['pasta', 'gehakt', 'italiaans'], 'bron': 'eigen'},
    {'naam': 'Pasta Carbonara', 'categorie': 'pasta', 'bereidingstijd': 20, 'porties': 4,
     'ingredienten': [{'naam': 'spaghetti', 'hoeveelheid': '400g'}, {'naam': 'spekblokjes', 'hoeveelheid': '200g'},
                      {'naam': 'eieren', 'hoeveelheid': '4'}, {'naam': 'parmezaanse kaas', 'hoeveelheid': '100g'},
                      {'naam': 'knoflook', 'hoeveelheid': '2 tenen'}, {'naam': 'zwarte peper', 'hoeveelheid': 'naar smaak'}],
     'instructies': ['Kook spaghetti al dente, bewaar kookvocht.', 'Bak spek krokant, voeg knoflook toe.',
                     'Klop eieren met parmezaan en peper.', 'Haal pan van vuur, voeg pasta toe.',
                     'Giet eimengsel erbij, roer snel. Voeg kookvocht toe voor romigheid.'],
     'tags': ['pasta', 'spek', 'italiaans', 'snel'], 'bron': 'eigen'},
    {'naam': 'Pasta Pesto met Kipfilet', 'categorie': 'pasta', 'bereidingstijd': 25, 'porties': 4,
     'ingredienten': [{'naam': 'penne', 'hoeveelheid': '400g'}, {'naam': 'kipfilet', 'hoeveelheid': '400g'},
                      {'naam': 'groene pesto', 'hoeveelheid': '150g'}, {'naam': 'cherrytomaatjes', 'hoeveelheid': '250g'},
                      {'naam': 'pijnboompitten', 'hoeveelheid': '50g'}, {'naam': 'rucola', 'hoeveelheid': '100g'}],
     'instructies': ['Snijd kip in reepjes, bak goudbruin.', 'Kook penne al dente.', 'Halveer cherrytomaatjes.',
                     'Rooster pijnboompitten droog.', 'Meng pasta met pesto, kip, tomaatjes, rucola en pijnboompitten.'],
     'tags': ['pasta', 'kip', 'pesto', 'snel'], 'bron': 'eigen'},
    {'naam': 'Stamppot Boerenkool', 'categorie': 'hollands', 'bereidingstijd': 40, 'porties': 4,
     'ingredienten': [{'naam': 'aardappelen', 'hoeveelheid': '1kg'}, {'naam': 'boerenkool', 'hoeveelheid': '500g'},
                      {'naam': 'rookworst', 'hoeveelheid': '4 stuks'}, {'naam': 'melk', 'hoeveelheid': '100ml'},
                      {'naam': 'roomboter', 'hoeveelheid': '50g'}, {'naam': 'spekjes', 'hoeveelheid': '150g'}],
     'instructies': ['Kook aardappelen gaar.', 'Kook boerenkool apart.', 'Verwarm rookworst in heet water.',
                     'Bak spekjes krokant.', 'Stamp aardappelen met melk en boter, meng met boerenkool.',
                     'Serveer met rookworst en spekjes.'],
     'tags': ['hollands', 'stamppot', 'worst', 'winter'], 'bron': 'eigen'},
    {'naam': 'Nasi Goreng', 'categorie': 'rijst', 'bereidingstijd': 30, 'porties': 4,
     'ingredienten': [{'naam': 'rijst', 'hoeveelheid': '300g'}, {'naam': 'kipfilet', 'hoeveelheid': '300g'},
                      {'naam': 'eieren', 'hoeveelheid': '4'}, {'naam': 'ui', 'hoeveelheid': '2'},
                      {'naam': 'knoflook', 'hoeveelheid': '3 tenen'}, {'naam': 'ketjap manis', 'hoeveelheid': '4 el'},
                      {'naam': 'sambal', 'hoeveelheid': 'naar smaak'}, {'naam': 'kroepoek', 'hoeveelheid': 'ter garnering'}],
     'instructies': ['Kook rijst, laat afkoelen.', 'Snijd kip in blokjes, bak gaar.', 'Snipper ui en knoflook, bak aan.',
                     'Voeg rijst toe, bak op hoog vuur.', 'Voeg ketjap en sambal toe.',
                     'Bak gebakken ei apart, serveer met kroepoek.'],
     'tags': ['rijst', 'kip', 'indonesisch', 'wok'], 'bron': 'eigen'},
    {'naam': 'Lasagne', 'categorie': 'pasta', 'bereidingstijd': 75, 'porties': 6,
     'ingredienten': [{'naam': 'lasagnebladen', 'hoeveelheid': '250g'}, {'naam': 'rundergehakt', 'hoeveelheid': '500g'},
                      {'naam': 'passata', 'hoeveelheid': '500ml'}, {'naam': 'bechamelsaus', 'hoeveelheid': '500ml'},
                      {'naam': 'ui', 'hoeveelheid': '1'}, {'naam': 'knoflook', 'hoeveelheid': '2 tenen'},
                      {'naam': 'geraspte kaas', 'hoeveelheid': '150g'}],
     'instructies': ['Maak ragu: bak gehakt met ui, knoflook en passata, 20 min sudderen.',
                     'Verwarm oven op 180°C.', 'Laag in ovenschaal: ragu, bladen, bechamel. Herhaal.',
                     'Eindig met bechamel en kaas.', 'Bak 40 min in oven tot goudbruin.'],
     'tags': ['pasta', 'gehakt', 'oven', 'italiaans'], 'bron': 'eigen'},
    {'naam': 'Kip Teriyaki met Rijst', 'categorie': 'rijst', 'bereidingstijd': 25, 'porties': 4,
     'ingredienten': [{'naam': 'kipfilet', 'hoeveelheid': '600g'}, {'naam': 'rijst', 'hoeveelheid': '300g'},
                      {'naam': 'teriyakisaus', 'hoeveelheid': '150ml'}, {'naam': 'broccoli', 'hoeveelheid': '300g'},
                      {'naam': 'sesamzaad', 'hoeveelheid': '2 el'}, {'naam': 'bosui', 'hoeveelheid': '2'}],
     'instructies': ['Kook rijst.', 'Snijd kip in blokjes, bak goudbruin.', 'Voeg teriyaki toe, karamelliseer.',
                     'Kook broccoli beetgaar.', 'Serveer kip op rijst met broccoli, garneer met sesam en bosui.'],
     'tags': ['rijst', 'kip', 'japans', 'gezond'], 'bron': 'eigen'},
    {'naam': 'Gehaktballen in Tomatensaus', 'categorie': 'hollands', 'bereidingstijd': 45, 'porties': 4,
     'ingredienten': [{'naam': 'rundergehakt', 'hoeveelheid': '500g'}, {'naam': 'ei', 'hoeveelheid': '1'},
                      {'naam': 'paneermeel', 'hoeveelheid': '50g'}, {'naam': 'passata', 'hoeveelheid': '400ml'},
                      {'naam': 'ui', 'hoeveelheid': '1'}, {'naam': 'knoflook', 'hoeveelheid': '2 tenen'}],
     'instructies': ['Meng gehakt met ei, paneermeel, zout, peper. Draai ballen.',
                     'Bak gehaktballen rondom bruin.', 'Maak saus: bak ui, knoflook, voeg passata toe.',
                     'Leg ballen in saus, 20 min sudderen.', 'Serveer met aardappelpuree.'],
     'tags': ['gehakt', 'hollands', 'comfort'], 'bron': 'eigen'},
    {'naam': 'Wraps met Kip', 'categorie': 'snel', 'bereidingstijd': 20, 'porties': 4,
     'ingredienten': [{'naam': 'tortilla wraps', 'hoeveelheid': '8'}, {'naam': 'kipfilet', 'hoeveelheid': '400g'},
                      {'naam': 'sla', 'hoeveelheid': '1 krop'}, {'naam': 'tomaat', 'hoeveelheid': '2'},
                      {'naam': 'komkommer', 'hoeveelheid': '1'}, {'naam': 'geraspte kaas', 'hoeveelheid': '100g'},
                      {'naam': 'yoghurtsaus', 'hoeveelheid': '100ml'}],
     'instructies': ['Snijd kip in reepjes, bak gaar.', 'Snijd groenten in reepjes.',
                     'Verwarm wraps kort.', 'Beleg met sla, kip, groenten, kaas en saus.', 'Rol op en serveer.'],
     'tags': ['snel', 'kip', 'wrap', 'lunch'], 'bron': 'eigen'},
    {'naam': 'Roerbakgroenten met Tofu', 'categorie': 'vegetarisch', 'bereidingstijd': 25, 'porties': 4,
     'ingredienten': [{'naam': 'tofu', 'hoeveelheid': '400g'}, {'naam': 'broccoli', 'hoeveelheid': '200g'},
                      {'naam': 'paprika', 'hoeveelheid': '2'}, {'naam': 'wortel', 'hoeveelheid': '2'},
                      {'naam': 'sojasaus', 'hoeveelheid': '3 el'}, {'naam': 'rijst', 'hoeveelheid': '300g'}],
     'instructies': ['Pers tofu uit, snijd in blokjes.', 'Bak tofu krokant in sesamolie.',
                     'Snijd groenten, roerbak op hoog vuur.', 'Voeg sojasaus toe, meng met tofu.',
                     'Serveer met rijst.'],
     'tags': ['vegetarisch', 'tofu', 'gezond', 'wok'], 'bron': 'eigen'},
    {'naam': 'Schnitzel met Friet', 'categorie': 'hollands', 'bereidingstijd': 30, 'porties': 4,
     'ingredienten': [{'naam': 'schnitzels', 'hoeveelheid': '4'}, {'naam': 'friet', 'hoeveelheid': '800g'},
                      {'naam': 'sla', 'hoeveelheid': '1 krop'}, {'naam': 'tomaat', 'hoeveelheid': '2'},
                      {'naam': 'mayonaise', 'hoeveelheid': 'naar smaak'}, {'naam': 'citroen', 'hoeveelheid': '1'}],
     'instructies': ['Bak friet in oven of frituur.', 'Bak schnitzels goudbruin in boter.',
                     'Maak salade van sla en tomaat.', 'Serveer met mayo en partje citroen.'],
     'tags': ['schnitzel', 'friet', 'hollands'], 'bron': 'eigen'},
    {'naam': 'Macaroni met Ham en Kaas', 'categorie': 'pasta', 'bereidingstijd': 25, 'porties': 4,
     'ingredienten': [{'naam': 'macaroni', 'hoeveelheid': '400g'}, {'naam': 'ham', 'hoeveelheid': '200g'},
                      {'naam': 'geraspte kaas', 'hoeveelheid': '200g'}, {'naam': 'melk', 'hoeveelheid': '200ml'},
                      {'naam': 'bloem', 'hoeveelheid': '2 el'}, {'naam': 'boter', 'hoeveelheid': '30g'}],
     'instructies': ['Kook macaroni al dente.', 'Maak roux van boter en bloem.',
                     'Voeg melk toe, roer tot gladde saus.', 'Voeg kaas toe, laat smelten.',
                     'Meng pasta, saus en ham.'],
     'tags': ['pasta', 'kaas', 'kindvriendelijk'], 'bron': 'eigen'},
    {'naam': 'Ovenschotel met Aardappel en Gehakt', 'categorie': 'oven', 'bereidingstijd': 60, 'porties': 4,
     'ingredienten': [{'naam': 'aardappelen', 'hoeveelheid': '1kg'}, {'naam': 'rundergehakt', 'hoeveelheid': '400g'},
                      {'naam': 'ui', 'hoeveelheid': '1'}, {'naam': 'tomatenpuree', 'hoeveelheid': '2 el'},
                      {'naam': 'geraspte kaas', 'hoeveelheid': '150g'}, {'naam': 'melk', 'hoeveelheid': '100ml'}],
     'instructies': ['Verwarm oven op 200°C.', 'Kook aardappelen gaar.',
                     'Bak gehakt met ui, voeg tomatenpuree toe.', 'Stamp aardappelen met melk.',
                     'Doe gehakt in schaal, puree erover, kaas erop.', 'Bak 25 min in oven.'],
     'tags': ['oven', 'gehakt', 'aardappel', 'comfort'], 'bron': 'eigen'},
    {'naam': 'Kipkerrie met Rijst', 'categorie': 'rijst', 'bereidingstijd': 35, 'porties': 4,
     'ingredienten': [{'naam': 'kipfilet', 'hoeveelheid': '500g'}, {'naam': 'rijst', 'hoeveelheid': '300g'},
                      {'naam': 'ui', 'hoeveelheid': '1'}, {'naam': 'kerrie', 'hoeveelheid': '2 el'},
                      {'naam': 'kokosmelk', 'hoeveelheid': '400ml'}, {'naam': 'paprika', 'hoeveelheid': '1'},
                      {'naam': 'doperwten', 'hoeveelheid': '150g'}],
     'instructies': ['Kook rijst.', 'Snijd kip in blokjes, bak aan.', 'Voeg ui en paprika toe.',
                     'Strooi kerrie erbij.', 'Voeg kokosmelk toe, 15 min sudderen.', 'Voeg doperwten toe, serveer.'],
     'tags': ['rijst', 'kip', 'kerrie', 'romig'], 'bron': 'eigen'},
    {'naam': 'Bami Goreng', 'categorie': 'noodles', 'bereidingstijd': 25, 'porties': 4,
     'ingredienten': [{'naam': 'bami', 'hoeveelheid': '400g'}, {'naam': 'kipfilet', 'hoeveelheid': '300g'},
                      {'naam': 'prei', 'hoeveelheid': '1'}, {'naam': 'wortel', 'hoeveelheid': '2'},
                      {'naam': 'kool', 'hoeveelheid': '200g'}, {'naam': 'ketjap manis', 'hoeveelheid': '4 el'}],
     'instructies': ['Kook bami volgens verpakking.', 'Snijd kip in reepjes, bak gaar.',
                     'Snijd groenten in dunne reepjes.', 'Roerbak groenten in wok.',
                     'Voeg bami en ketjap toe.', 'Serveer met gebakken ei.'],
     'tags': ['noodles', 'kip', 'indonesisch', 'wok'], 'bron': 'eigen'},
]

def create_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recepten (
            id SERIAL PRIMARY KEY,
            naam VARCHAR(200) NOT NULL,
            categorie VARCHAR(50),
            bereidingstijd INTEGER,
            porties INTEGER,
            ingredienten JSONB,
            instructies JSONB,
            tags JSONB,
            bron VARCHAR(100),
            external_id VARCHAR(50),
            afbeelding VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(naam, bron)
        )
    ''')
    conn.commit()
    conn.close()

def clear_recipes():
    """Maak recepten tabel leeg voor verse sync"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM recepten")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted

def sync_dutch_recipes():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    inserted = 0
    for r in DUTCH_RECIPES:
        try:
            cur.execute('''
                INSERT INTO recepten (naam, categorie, bereidingstijd, porties, ingredienten, instructies, tags, bron)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (naam, bron) DO UPDATE SET ingredienten = EXCLUDED.ingredienten, instructies = EXCLUDED.instructies
            ''', (r['naam'], r['categorie'], r['bereidingstijd'], r['porties'],
                  Json(r['ingredienten']), Json(r['instructies']), Json(r['tags']), r['bron']))
            inserted += 1
        except Exception as e:
            print(f"Fout: {e}")
    conn.commit()
    conn.close()
    return inserted

def fetch_mealdb_recipes():
    recipes = []
    categories = ['Beef', 'Chicken', 'Pasta', 'Pork', 'Seafood', 'Vegetarian', 'Lamb', 'Miscellaneous']
    for cat in categories:
        try:
            resp = requests.get(f"{MEALDB_BASE}/filter.php?c={cat}", timeout=10)
            data = resp.json()
            if data.get('meals'):
                for meal in data['meals'][:12]:
                    detail_resp = requests.get(f"{MEALDB_BASE}/lookup.php?i={meal['idMeal']}", timeout=10)
                    detail = detail_resp.json()
                    if detail.get('meals'):
                        recipes.append(detail['meals'][0])
                    time.sleep(0.2)
        except Exception as e:
            print(f"Fout bij {cat}: {e}")
    return recipes

def parse_mealdb_recipe(meal):
    ingredienten = []
    for i in range(1, 21):
        ing = meal.get(f'strIngredient{i}')
        measure = meal.get(f'strMeasure{i}')
        if ing and ing.strip():
            ingredienten.append({'naam': ing.strip(), 'hoeveelheid': measure.strip() if measure else ''})
    instructies = [s.strip() for s in meal.get('strInstructions', '').split('\r\n') if s.strip()]
    tags = []
    if meal.get('strTags'):
        tags = [t.strip().lower() for t in meal['strTags'].split(',')]
    if meal.get('strArea'):
        tags.append(meal['strArea'].lower())
    if meal.get('strCategory'):
        tags.append(meal['strCategory'].lower())
    return {
        'naam': meal.get('strMeal', ''), 'categorie': meal.get('strCategory', '').lower(),
        'bereidingstijd': 30, 'porties': 4, 'ingredienten': ingredienten, 'instructies': instructies,
        'tags': tags, 'bron': 'themealdb', 'external_id': meal.get('idMeal'), 'afbeelding': meal.get('strMealThumb')
    }

def sync_mealdb_recipes():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Ophalen recepten van TheMealDB...")
    meals = fetch_mealdb_recipes()
    print(f"  {len(meals)} recepten opgehaald")
    inserted = 0
    for meal in meals:
        r = parse_mealdb_recipe(meal)
        try:
            cur.execute('''
                INSERT INTO recepten (naam, categorie, bereidingstijd, porties, ingredienten, instructies, tags, bron, external_id, afbeelding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (naam, bron) DO UPDATE SET ingredienten = EXCLUDED.ingredienten, afbeelding = EXCLUDED.afbeelding
            ''', (r['naam'], r['categorie'], r['bereidingstijd'], r['porties'],
                  Json(r['ingredienten']), Json(r['instructies']), Json(r['tags']),
                  r['bron'], r['external_id'], r['afbeelding']))
            inserted += 1
        except Exception as e:
            print(f"Fout: {e}")
    conn.commit()
    conn.close()
    return inserted

def main():
    print("=" * 60)
    print("Recepten Sync")
    print("=" * 60)
    create_tables()
    
    # EERST LEGEN
    deleted = clear_recipes()
    print(f"Verwijderd: {deleted} oude recepten\n")
    
    print("1. Nederlandse recepten...")
    dutch = sync_dutch_recipes()
    print(f"   {dutch} recepten toegevoegd")
    
    print("\n2. TheMealDB recepten...")
    mealdb = sync_mealdb_recipes()
    print(f"   {mealdb} recepten toegevoegd")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT bron, COUNT(*) FROM recepten GROUP BY bron")
    print("\nResultaat:")
    for row in cur.fetchall():
        print(f"  {row[0]:15} {row[1]:3} recepten")
    cur.execute("SELECT COUNT(*) FROM recepten")
    print(f"\nTotaal: {cur.fetchone()[0]} recepten")
    conn.close()
    print("=" * 60)

if __name__ == '__main__':
    main()
