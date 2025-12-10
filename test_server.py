#!/usr/bin/env python3
"""
Test script voor de NL Supermarkt MCP Server (Extended Edition)
Run: python test_server.py
"""

import asyncio
import sys
sys.path.insert(0, '.')

from src.server import CheckjebonClient, RecipeParser, SupermarketLocator, PriceHistoryDB


async def main():
    print("🧪 Testing NL Supermarkt MCP Server - Extended Edition\n")
    print("=" * 60)
    
    # Use mock mode for demo
    db = PriceHistoryDB()
    client = CheckjebonClient(use_mock=True, db=db)
    
    # Test 1: Supermarkten
    print("\n1️⃣ Ophalen van supermarkten...")
    try:
        supermarkets = await client.get_supermarkets()
        print(f"   ✅ {len(supermarkets)} supermarkten gevonden")
        for sm in supermarkets[:3]:
            print(f"      {sm['icon']} {sm['name']}: {sm['product_count']} producten")
    except Exception as e:
        print(f"   ❌ Fout: {e}")
    
    # Test 2: Zoek producten
    print("\n2️⃣ Zoeken naar 'halfvolle melk'...")
    try:
        results = await client.search_products("halfvolle melk")
        print(f"   ✅ {len(results)} resultaten")
        for r in results[:3]:
            discount = " 🏷️" if r.get("is_discount") else ""
            print(f"      {r['supermarket_icon']} {r['supermarket_name']}: €{r['price']:.2f}{discount}")
    except Exception as e:
        print(f"   ❌ Fout: {e}")
    
    # Test 3: Aanbiedingen
    print("\n3️⃣ Ophalen aanbiedingen...")
    try:
        discounts = await client.get_discounts()
        print(f"   ✅ {len(discounts)} aanbiedingen gevonden")
        for d in discounts[:3]:
            print(f"      {d['supermarket_icon']} {d['name']}: €{d['original_price']:.2f} → €{d['price']:.2f} (-{d['discount_percent']}%)")
    except Exception as e:
        print(f"   ❌ Fout: {e}")
    
    # Test 4: Recept parser
    print("\n4️⃣ Recept parser testen...")
    try:
        recept = """
        500g gehakt
        1 ui
        2 tenen knoflook
        400g tomatenblokjes
        500g spaghetti
        100g kaas
        """
        ingredients = RecipeParser.parse_recipe(recept)
        print(f"   ✅ {len(ingredients)} ingrediënten geparsed:")
        for ing in ingredients:
            qty = f"{ing['quantity']} {ing['unit'] or ''}" if ing['quantity'] else ""
            print(f"      - {qty} {ing['ingredient']}")
    except Exception as e:
        print(f"   ❌ Fout: {e}")
    
    # Test 5: Optimalisatie
    print("\n5️⃣ Boodschappenlijst optimaliseren...")
    try:
        products = ["melk", "brood", "kaas", "eieren", "kipfilet"]
        result = await client.optimize_shopping_list(products)
        print(f"   ✅ Totaal: €{result['total_cost']:.2f} bij {result['stores_needed']} winkel(s)")
        for sm_code, plan in result.get("shopping_plan", {}).items():
            print(f"      {plan['supermarket_icon']} {plan['supermarket_name']}: €{plan['subtotal']:.2f}")
    except Exception as e:
        print(f"   ❌ Fout: {e}")
    
    # Test 6: Locaties (mock)
    print("\n6️⃣ Supermarkten zoeken bij Amsterdam Centraal...")
    try:
        locations = await SupermarketLocator.find_nearby_supermarkets(52.3791, 4.9003, 2)
        print(f"   ✅ {len(locations)} supermarkten gevonden (mock data)")
        for loc in locations[:3]:
            print(f"      🏪 {loc['name']}: {loc['distance_km']}km")
    except Exception as e:
        print(f"   ❌ Fout: {e}")
    
    # Test 7: Prijshistorie
    print("\n7️⃣ Prijshistorie testen...")
    try:
        # Record some mock prices
        db.record_price("AH Melk", "ah", 1.35, "1L")
        db.record_price("AH Melk", "ah", 1.29, "1L")
        trend = client.get_price_trend("Melk")
        print(f"   ✅ Trend: {trend['trend']}, {trend['data_points']} data punten")
    except Exception as e:
        print(f"   ❌ Fout: {e}")
    
    print("\n" + "=" * 60)
    print("✨ Alle tests voltooid!")
    print("\n📋 Beschikbare tools:")
    print("   • zoek_producten")
    print("   • vergelijk_prijzen")
    print("   • optimaliseer_boodschappenlijst")
    print("   • lijst_supermarkten")
    print("   • bekijk_aanbiedingen        [NEW]")
    print("   • recept_naar_boodschappen   [NEW]")
    print("   • bekijk_prijshistorie       [NEW]")
    print("   • vind_supermarkten_dichtbij [NEW]")


if __name__ == "__main__":
    asyncio.run(main())
