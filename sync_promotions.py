#!/usr/bin/env python3
"""
Sync aanbiedingen van AH en Jumbo naar PostgreSQL
"""

import psycopg2
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DB_CONFIG = {'database': 'supermarkt_db', 'user': 'postgres', 'port': 5433, 'host': '127.0.0.1'}

def sync_ah_promotions():
    """Sync Albert Heijn bonus producten"""
    from supermarktconnector.ah import AHConnector
    
    logger.info('Fetching AH bonus products...')
    connector = AHConnector()
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    count = 0
    try:
        for product in connector.get_all_bonus_products():
            try:
                name = product.get('title', '')
                if not name:
                    continue
                
                # Prijzen
                price_info = product.get('priceBeforeBonus', {})
                original_price = price_info.get('now', 0) if price_info else 0
                
                bonus_price_info = product.get('currentPrice', {})
                discount_price = bonus_price_info.get('now', 0) if bonus_price_info else 0
                
                if not discount_price:
                    continue
                
                # Korting percentage berekenen
                discount_percent = None
                if original_price and original_price > discount_price:
                    discount_percent = int((1 - discount_price / original_price) * 100)
                
                # Bonus type
                bonus_info = product.get('bonusMechanism', '')
                shield = product.get('shield', {})
                promo_type = shield.get('text', bonus_info) if shield else bonus_info
                
                # Periode
                bonus_period = product.get('bonusPeriodDescription', '')
                # Standaard huidige week
                start_date = date.today()
                end_date = None  # Wordt later bepaald
                
                # Image
                images = product.get('images', [])
                image_url = images[0].get('url', '') if images else ''
                
                cur.execute('''
                    INSERT INTO promotions 
                    (supermarket_code, product_name, original_price, discount_price, 
                     discount_percent, promo_type, start_date, end_date, product_image)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (supermarket_code, product_name, start_date) 
                    DO UPDATE SET 
                        original_price = EXCLUDED.original_price,
                        discount_price = EXCLUDED.discount_price,
                        discount_percent = EXCLUDED.discount_percent,
                        promo_type = EXCLUDED.promo_type
                ''', ('ah', name, original_price, discount_price, discount_percent, 
                      promo_type, start_date, end_date, image_url))
                count += 1
                
            except Exception as e:
                logger.warning(f'Error processing AH product: {e}')
                continue
                
    except Exception as e:
        logger.error(f'Error fetching AH promotions: {e}')
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f'  AH: {count} bonus producten')
    return count

def sync_jumbo_promotions():
    """Sync Jumbo promoties"""
    from supermarktconnector.jumbo import JumboConnector
    
    logger.info('Fetching Jumbo promotions...')
    connector = JumboConnector()
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    count = 0
    try:
        promotions = connector.get_all_promotions()
        
        for tab in promotions.get('tabs', []):
            for item in tab.get('items', []):
                try:
                    product = item.get('product', {})
                    if not product:
                        continue
                    
                    name = product.get('title', '')
                    if not name:
                        continue
                    
                    # Prijzen
                    prices = product.get('prices', {})
                    original_price = prices.get('price', {}).get('amount', 0)
                    promo_price = prices.get('promotionalPrice', {}).get('amount', 0)
                    discount_price = promo_price if promo_price else original_price
                    
                    # Korting
                    discount_percent = None
                    if original_price and promo_price and original_price > promo_price:
                        discount_percent = int((1 - promo_price / original_price) * 100)
                    
                    # Promo type
                    promo_type = item.get('tag', {}).get('text', 'Aanbieding')
                    
                    # Image
                    image_url = product.get('imageInfo', {}).get('primaryView', [{}])[0].get('url', '')
                    
                    start_date = date.today()
                    
                    cur.execute('''
                        INSERT INTO promotions 
                        (supermarket_code, product_name, original_price, discount_price, 
                         discount_percent, promo_type, start_date, product_image)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (supermarket_code, product_name, start_date) 
                        DO UPDATE SET 
                            original_price = EXCLUDED.original_price,
                            discount_price = EXCLUDED.discount_price,
                            discount_percent = EXCLUDED.discount_percent,
                            promo_type = EXCLUDED.promo_type
                    ''', ('jumbo', name, original_price, discount_price, discount_percent, 
                          promo_type, start_date, image_url))
                    count += 1
                    
                except Exception as e:
                    logger.warning(f'Error processing Jumbo product: {e}')
                    continue
                    
    except Exception as e:
        logger.error(f'Error fetching Jumbo promotions: {e}')
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f'  Jumbo: {count} promoties')
    return count

def cleanup_old_promotions():
    """Verwijder verlopen aanbiedingen"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Verwijder aanbiedingen ouder dan 7 dagen
    cur.execute('''
        DELETE FROM promotions 
        WHERE start_date < CURRENT_DATE - INTERVAL '7 days'
    ''')
    deleted = cur.rowcount
    
    conn.commit()
    cur.close()
    conn.close()
    
    if deleted:
        logger.info(f'  Cleanup: {deleted} oude aanbiedingen verwijderd')

def main():
    logger.info('=== Syncing promotions ===')
    
    ah_count = sync_ah_promotions()
    jumbo_count = sync_jumbo_promotions()
    cleanup_old_promotions()
    
    logger.info(f'Totaal: {ah_count + jumbo_count} aanbiedingen gesynchroniseerd')
    logger.info('=== Done ===')

if __name__ == '__main__':
    main()
