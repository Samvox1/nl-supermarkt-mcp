#!/usr/bin/env python3
"""Master sync script voor Docker - kan alle syncs of specifieke syncs draaien"""

import os
import sys
import time
import psycopg2

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'db'),
    'port': int(os.environ.get('DB_PORT', '5432')),
    'database': os.environ.get('DB_NAME', 'supermarkt_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'supermarkt123')
}

def wait_for_db():
    print('Wachten op database...')
    for i in range(30):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.close()
            print('Database beschikbaar!')
            return True
        except:
            time.sleep(2)
    print('Database niet beschikbaar na 60 seconden')
    return False

def patch_db_config(module_name):
    """Patch DB_CONFIG in een sync module"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, f'{module_name}.py')
    module = importlib.util.module_from_spec(spec)
    module.DB_CONFIG = DB_CONFIG
    spec.loader.exec_module(module)
    return module

def run_sync(sync_type):
    """Run een specifieke sync"""
    print(f'\n{"="*60}')
    print(f'Starting {sync_type} sync...')
    print(f'{"="*60}')
    
    try:
        if sync_type == 'prices':
            module = patch_db_config('sync_prices')
            module.main()
        elif sync_type == 'folderz':
            module = patch_db_config('sync_folderz')
            module.main()
        elif sync_type == 'recepten':
            module = patch_db_config('sync_recepten')
            module.main()
        else:
            print(f'Onbekende sync type: {sync_type}')
            return False
        print(f'{sync_type} sync voltooid!')
        return True
    except Exception as e:
        print(f'Fout bij {sync_type} sync: {e}')
        return False

def main():
    if not wait_for_db():
        sys.exit(1)
    
    # Check of specifieke sync gevraagd wordt
    if len(sys.argv) > 1:
        sync_type = sys.argv[1]
        success = run_sync(sync_type)
        sys.exit(0 if success else 1)
    
    # Anders alle syncs draaien
    print('\nStarting all syncs...')
    
    syncs = ['prices', 'folderz', 'recepten']
    results = {}
    
    for sync in syncs:
        results[sync] = run_sync(sync)
    
    # Summary
    print(f'\n{"="*60}')
    print('SYNC SUMMARY')
    print(f'{"="*60}')
    for sync, success in results.items():
        status = 'OK' if success else 'FAILED'
        print(f'  {sync:15} {status}')
    
    # Database stats
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM products')
        products = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM promotions')
        promotions = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM recepten')
        recepten = cur.fetchone()[0]
        conn.close()
        
        print(f'\nDatabase:')
        print(f'  Producten:  {products:,}')
        print(f'  Promoties:  {promotions:,}')
        print(f'  Recepten:   {recepten:,}')
    except Exception as e:
        print(f'Kon database stats niet ophalen: {e}')
    
    print(f'{"="*60}')

if __name__ == '__main__':
    main()
