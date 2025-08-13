#!/usr/bin/env python3
"""
Check the current state of synthetic test data in the database
"""

import asyncio
import sys
import os

sys.path.insert(0, '/home/ubuntu/universal-db/rss_ingestion')
os.chdir('/home/ubuntu/universal-db/rss_ingestion')

from app.services import DatabaseService

async def check_data():
    db_service = DatabaseService()
    await db_service.init_db()
    
    all_records = await db_service.get_records('default', limit=1000)
    staged_records = [r for r in all_records if r.get('schema_id') == 'staged_rss_item']
    test_records = [r for r in staged_records if r.get('data', {}).get('staging_metadata', {}).get('test_data')]
    
    print(f'Total records in database: {len(all_records)}')
    print(f'Staged records (schema_id=staged_rss_item): {len(staged_records)}')
    print(f'Test data records: {len(test_records)}')
    
    by_category = {}
    for record in test_records:
        category = record.get('data', {}).get('staging_metadata', {}).get('category', 'Unknown')
        by_category[category] = by_category.get(category, 0) + 1
    
    print('\nTest records by category:')
    for category, count in by_category.items():
        print(f'  {category}: {count}')
    
    if test_records:
        sample = test_records[0]
        print(f'\nSample record structure:')
        print(f'  UUID: {sample.get("uuid")}')
        print(f'  Schema ID: {sample.get("schema_id")}')
        print(f'  Title: {sample.get("data", {}).get("title", "N/A")}')
        print(f'  Domain ID: {sample.get("data", {}).get("staging_metadata", {}).get("domain_id")}')
        print(f'  Expected Outcome: {sample.get("data", {}).get("staging_metadata", {}).get("expected_outcome")}')
    
    return {
        'total_records': len(all_records),
        'staged_records': len(staged_records), 
        'test_records': len(test_records),
        'by_category': by_category
    }

if __name__ == "__main__":
    result = asyncio.run(check_data())
    print(f'\nData status: {result}')
