#!/usr/bin/env python3
"""
Test Data Ingestion Script for Universal Database

Ingests synthetic test data as staged records for promotion testing.
"""

import asyncio
import json
import sys
import os
from datetime import datetime
import hashlib

sys.path.insert(0, '/home/ubuntu/universal-db/rss_ingestion')
os.chdir('/home/ubuntu/universal-db/rss_ingestion')

from app.services import DatabaseService, VectorService, DomainService, RSSService
from app.models import UniversalWrapper, Source, RSSItem, CreateDomainRequest


async def create_test_domains(domain_service: DomainService):
    """Create test domains for filtering"""
    
    domains = [
        {
            'name': 'Fort Worth Political',
            'description': 'Fort Worth city politics, government, and municipal affairs',
            'keywords': ['fort worth', 'city council', 'mayor', 'municipal', 'government', 'politics', 'tarrant county'],
            'entities': ['Fort Worth', 'City Council', 'Mayor', 'Tarrant County'],
            'locations': ['Fort Worth', 'Texas', 'Tarrant County'],
            'exclude_keywords': ['sports', 'entertainment', 'celebrity', 'movie'],
            'min_relevance_score': 0.3
        },
        {
            'name': 'Tech Startups',
            'description': 'Technology startups, venture capital, and innovation',
            'keywords': ['startup', 'venture capital', 'funding', 'tech', 'innovation', 'entrepreneur'],
            'entities': ['startup', 'VC', 'venture capital', 'entrepreneur'],
            'locations': ['Silicon Valley', 'Austin', 'Dallas'],
            'exclude_keywords': ['sports', 'politics', 'celebrity'],
            'min_relevance_score': 0.3
        },
        {
            'name': 'Mixed Content',
            'description': 'Mixed content with some business and innovation focus',
            'keywords': ['business', 'innovation', 'local'],
            'entities': ['business', 'company'],
            'locations': ['Texas', 'Dallas'],
            'exclude_keywords': ['celebrity', 'gossip', 'sports'],
            'min_relevance_score': 0.3
        },
        {
            'name': 'Noise Heavy',
            'description': 'General content with very specific filtering',
            'keywords': ['policy', 'announcement', 'official'],
            'entities': ['government', 'official'],
            'locations': [],
            'exclude_keywords': ['recipe', 'movie', 'horoscope', 'celebrity', 'sports'],
            'min_relevance_score': 0.4
        }
    ]
    
    created_domains = {}
    
    for domain_data in domains:
        request = CreateDomainRequest(**domain_data)
        domain = await domain_service.create_domain(request)
        created_domains[domain_data['name']] = domain.domain_id
        print(f"Created domain: {domain_data['name']} ({domain.domain_id})")
    
    return created_domains


async def ingest_test_dataset():
    """Ingest synthetic test data as staged records"""
    
    print("Initializing services...")
    db_service = DatabaseService()
    vector_service = VectorService()
    domain_service = DomainService()
    rss_service = RSSService(db_service, vector_service, domain_service)
    
    await db_service.init_db()
    await vector_service.init_collection()
    
    print("Creating test domains...")
    domain_mapping = await create_test_domains(domain_service)
    
    print("Loading test dataset...")
    with open('/home/ubuntu/universal-db/test_dataset.json', 'r') as f:
        dataset = json.load(f)
    
    total_ingested = 0
    
    category_to_domain = {
        'fort_worth_political': 'Fort Worth Political',
        'tech_startups': 'Tech Startups', 
        'mixed_content': 'Mixed Content',
        'noise_heavy': 'Noise Heavy'
    }
    
    for category, articles in dataset['articles'].items():
        print(f"\nIngesting {len(articles)} articles from {category}...")
        
        domain_name = category_to_domain.get(category)
        domain_id = domain_mapping.get(domain_name) if domain_name else None
        
        if not domain_id:
            print(f"Warning: No domain found for category {category} (mapped to {domain_name})")
            continue
        
        for i, article in enumerate(articles):
            try:
                rss_item = RSSItem(
                    title=article['title'],
                    description=article['description'],
                    link=article['link'],
                    published=datetime.fromisoformat(article['published']) if article['published'] else None,
                    content=article.get('content', ''),
                    author=article.get('author', ''),
                    tags=article.get('tags', [])
                )
                
                content_text = f"{rss_item.title} {rss_item.description or ''} {rss_item.content or ''}"
                content_hash = hashlib.md5(content_text.encode()).hexdigest()
                
                rss_data = rss_item.model_dump()
                rss_data['staging_metadata'] = {
                    'domain_id': domain_id,
                    'requires_domain_filtering': True,
                    'ingestion_timestamp': datetime.utcnow().isoformat(),
                    'test_data': True,
                    'expected_outcome': article.get('expected_outcome', 'UNKNOWN'),
                    'category': category
                }
                
                wrapper = UniversalWrapper(
                    schema_id="staged_rss_item",
                    tenant_id="default",
                    source=Source(origin=f"test_data_{category}", type="rss"),
                    data=rss_data
                )
                
                saved = await db_service.save_record(wrapper, content_hash)
                
                if saved:
                    embedding_text = f"{rss_item.title} {rss_item.description or ''} {rss_item.content or ''}"
                    embedding = await vector_service.generate_embedding(embedding_text)
                    
                    if embedding:
                        metadata = {
                            "tenant_id": "default",
                            "schema_id": "staged_rss_item",
                            "title": rss_item.title,
                            "link": rss_item.link,
                            "published": rss_item.published.isoformat() if rss_item.published else None,
                            "domain_id": domain_id,
                            "requires_filtering": True,
                            "test_data": True,
                            "expected_outcome": article.get('expected_outcome', 'UNKNOWN'),
                            "category": category
                        }
                        await vector_service.save_vector(wrapper.uuid, embedding, metadata)
                    
                    total_ingested += 1
                    if (i + 1) % 10 == 0:
                        print(f"  Ingested {i + 1}/{len(articles)} articles from {category}")
                
            except Exception as e:
                print(f"Error ingesting article {i} from {category}: {e}")
    
    print(f"\nIngestion complete! Total articles ingested: {total_ingested}")
    
    print("\nVerifying ingestion...")
    all_records = await db_service.get_records("default", limit=1000)
    staged_records = [r for r in all_records if r.get('schema_id') == 'staged_rss_item']
    test_records = [r for r in staged_records if r.get('data', {}).get('staging_metadata', {}).get('test_data')]
    
    print(f"Total records in database: {len(all_records)}")
    print(f"Staged records: {len(staged_records)}")
    print(f"Test records: {len(test_records)}")
    
    by_category = {}
    for record in test_records:
        category = record.get('data', {}).get('staging_metadata', {}).get('category', 'Unknown')
        by_category[category] = by_category.get(category, 0) + 1
    
    print("Records by category:")
    for category, count in by_category.items():
        print(f"  {category}: {count}")
    
    return {
        'total_ingested': total_ingested,
        'total_records': len(all_records),
        'staged_records': len(staged_records),
        'test_records': len(test_records),
        'by_category': by_category,
        'domain_mapping': domain_mapping
    }


if __name__ == "__main__":
    result = asyncio.run(ingest_test_dataset())
    print(f"\nFinal result: {result}")
