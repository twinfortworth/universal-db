from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from .models import (
    IngestRSSRequest, SearchRequest, SearchResult, CreateDomainRequest, 
    DomainIngestRequest, DomainAnalytics, DomainEntity, EntityType,
    CreateRSSFeedRequest, UpdateRSSFeedRequest, RSSFeedListResponse, FeedUpdateResult, RSSFeed,
    ManualFilterRequest, PromotionRequest, PromotionResult, PromotionStatistics,
    UniversalWrapper, RSSItem, Source
)
from .services import DatabaseService, VectorService, RSSService, DomainService, RSSFeedService
from .promotion_service import RecordPromotionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_service = DatabaseService()
vector_service = VectorService()
domain_service = DomainService()
rss_service = RSSService(db_service, vector_service, domain_service)
rss_feed_service = RSSFeedService(db_service, rss_service, domain_service)
promotion_service = RecordPromotionService(db_service, domain_service, vector_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing databases...")
    await db_service.init_db()
    await vector_service.init_collection()
    
    logger.info(f"DEBUG: RSS service type: {type(rss_service)}")
    logger.info(f"DEBUG: RSS service has ingest_rss_feed_with_domain: {hasattr(rss_service, 'ingest_rss_feed_with_domain')}")
    if hasattr(rss_service, 'ingest_rss_feed_with_domain'):
        logger.info(f"DEBUG: Method type: {type(rss_service.ingest_rss_feed_with_domain)}")
    else:
        logger.error("DEBUG: ingest_rss_feed_with_domain method NOT FOUND!")
        logger.info(f"DEBUG: Available methods: {[method for method in dir(rss_service) if not method.startswith('_')]}")
    
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title="Universal Database - RSS Ingestion",
    description="A universal database system starting with RSS feed ingestion",
    version="1.0.0",
    lifespan=lifespan
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/health/embeddings")
async def check_embedding_health():
    """Health check for embedding generation"""
    try:
        test_texts = ["football sports game", "japanese culture technology", "politics government policy"]
        embeddings = []
        
        for text in test_texts:
            embedding = await vector_service.generate_embedding(text)
            if embedding:
                embeddings.append({"text": text, "embedding_length": len(embedding), "first_few": embedding[:5]})
            else:
                return {"status": "error", "message": f"Failed to generate embedding for: {text}"}
        
        return {"status": "healthy", "embedding_model": "working", "test_embeddings": embeddings}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/ingest/rss")
async def ingest_rss_feed(request: IngestRSSRequest):
    """Ingest an RSS feed and store items in universal wrapper format"""
    try:
        result = await rss_service.ingest_rss_feed(request.feed_url, request.tenant_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"RSS ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/records")
async def get_records(tenant_id: str = "default", limit: int = 10, offset: int = 0):
    """Get stored records with pagination"""
    try:
        records = await db_service.get_records(tenant_id, limit, offset)
        return {
            "records": records,
            "count": len(records),
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search_records(request: SearchRequest):
    """Semantic search using vector similarity"""
    try:
        query_embedding = await vector_service.generate_embedding(request.query)
        if not query_embedding:
            raise HTTPException(status_code=400, detail="Failed to generate embedding for query")
        
        vector_results = await vector_service.search_vectors(
            query_embedding, request.tenant_id, request.limit
        )
        
        search_results = []
        for result in vector_results:
            metadata = result["metadata"]
            search_results.append(SearchResult(
                uuid=result["uuid"],
                title=metadata.get("title", ""),
                description=metadata.get("description"),
                link=metadata.get("link", ""),
                score=result["score"],
                published=metadata.get("published")
            ))
        
        return {
            "query": request.query,
            "results": search_results,
            "count": len(search_results)
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/hybrid")
async def hybrid_search_records(request: SearchRequest):
    """Advanced search using hybrid search (BM25 + vector similarity) with re-ranking"""
    try:
        hybrid_results = await vector_service.hybrid_search(
            request.query, request.tenant_id, request.limit * 2,
            request.bm25_weight, request.vector_weight
        )
        
        if request.use_reranking:
            reranked_results = await vector_service.rerank_results(
                request.query, hybrid_results, request.limit
            )
        else:
            reranked_results = hybrid_results[:request.limit]
        
        search_results = []
        for result in reranked_results:
            metadata = result["metadata"]
            search_results.append(SearchResult(
                uuid=result["uuid"],
                title=metadata.get("title", ""),
                description=metadata.get("description"),
                link=metadata.get("link", ""),
                score=result.get("rerank_score", result.get("rrf_score", 0.0)),
                published=metadata.get("published")
            ))
        
        return {
            "query": request.query,
            "search_type": "hybrid_with_reranking" if request.use_reranking else "hybrid",
            "results": search_results,
            "count": len(search_results)
        }
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/domains")
async def create_domain(request: CreateDomainRequest):
    try:
        domain = await domain_service.create_domain(request)
        return domain
    except Exception as e:
        logger.error(f"Failed to create domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/domains")
async def list_domains():
    try:
        domains = await domain_service.list_domains()
        return {"domains": domains, "count": len(domains)}
    except Exception as e:
        logger.error(f"Failed to list domains: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/domains/{domain_id}")
async def get_domain(domain_id: str):
    try:
        domain = await domain_service.get_domain(domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        return domain
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/rss/domain")
async def ingest_rss_with_domain(request: DomainIngestRequest):
    try:
        rss_service.current_domain_id = request.domain_id
        result = await rss_service.ingest_rss_feed(request.feed_url, request.tenant_id)
        rss_service.current_domain_id = None  # Reset context
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Domain RSS ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/domains/{domain_id}")
async def update_domain(domain_id: str, request: CreateDomainRequest):
    """Update domain"""
    try:
        updates = request.model_dump(exclude_unset=True)
        domain = await domain_service.update_domain(domain_id, updates)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        return domain
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/domains/{domain_id}")
async def delete_domain(domain_id: str):
    """Delete domain"""
    try:
        success = await domain_service.delete_domain(domain_id)
        if not success:
            raise HTTPException(status_code=404, detail="Domain not found")
        return {"message": "Domain deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/domain/{domain_id}")
async def get_domain_analytics(domain_id: str, tenant_id: str = "default"):
    try:
        domain = await domain_service.get_domain(domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        
        all_records = await db_service.get_records(tenant_id, limit=1000)
        domain_records = [r for r in all_records if r.get("data", {}).get("domain_tags", []) and domain.name in r["data"]["domain_tags"]]
        
        total_articles = len(all_records)
        relevant_articles = len(domain_records)
        relevance_rate = relevant_articles / max(total_articles, 1)
        
        entity_counts = {}
        for record in domain_records:
            entities = record.get("data", {}).get("entities", [])
            for entity in entities:
                name = entity.get("name", "")
                if name:
                    entity_counts[name] = entity_counts.get(name, 0) + 1
        
        top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        analytics = DomainAnalytics(
            total_articles=total_articles,
            relevant_articles=relevant_articles,
            relevance_rate=relevance_rate,
            top_entities=[DomainEntity(name=name, type=EntityType.PERSON, confidence=0.8) for name, _ in top_entities],
            new_entities=[],
            trending_topics=list(domain.keywords[:5]),
            time_period="all_time"
        )
        
        return analytics
    except Exception as e:
        logger.error(f"Failed to get domain analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/feeds", response_model=RSSFeed)
async def create_rss_feed(request: CreateRSSFeedRequest):
    """Create a new RSS feed"""
    try:
        feed = await rss_feed_service.create_feed(request)
        return feed
    except Exception as e:
        logger.error(f"Failed to create RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feeds", response_model=RSSFeedListResponse)
async def list_rss_feeds(tenant_id: str = "default", page: int = 1, page_size: int = 10):
    """List RSS feeds with pagination"""
    try:
        return await rss_feed_service.list_feeds(tenant_id, page, page_size)
    except Exception as e:
        logger.error(f"Failed to list RSS feeds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feeds/{feed_id}")
async def get_rss_feed(feed_id: str):
    """Get RSS feed by ID"""
    try:
        feed = await rss_feed_service.get_feed(feed_id)
        if not feed:
            raise HTTPException(status_code=404, detail="RSS feed not found")
        return feed
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/feeds/{feed_id}")
async def update_rss_feed(feed_id: str, request: UpdateRSSFeedRequest):
    """Update RSS feed"""
    try:
        feed = await rss_feed_service.update_feed(feed_id, request)
        if not feed:
            raise HTTPException(status_code=404, detail="RSS feed not found")
        return feed
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/feeds/{feed_id}")
async def delete_rss_feed(feed_id: str):
    """Delete RSS feed"""
    try:
        success = await rss_feed_service.delete_feed(feed_id)
        if not success:
            raise HTTPException(status_code=404, detail="RSS feed not found")
        return {"message": "RSS feed deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feeds/{feed_id}/toggle")
async def toggle_rss_feed(feed_id: str):
    """Toggle RSS feed active status"""
    try:
        feed = await rss_feed_service.toggle_feed_status(feed_id)
        if not feed:
            raise HTTPException(status_code=404, detail="RSS feed not found")
        return feed
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feeds/{feed_id}/update", response_model=FeedUpdateResult)
async def update_rss_feed_manually(feed_id: str):
    """Manually trigger RSS feed update"""
    logger.info(f"DEBUG: Manual update endpoint called for feed_id: {feed_id}")
    logger.info(f"DEBUG: rss_feed_service type: {type(rss_feed_service)}")
    logger.info(f"DEBUG: rss_feed_service.rss_service type: {type(rss_feed_service.rss_service)}")
    logger.info(f"DEBUG: rss_feed_service.rss_service has ingest_rss_feed_with_domain: {hasattr(rss_feed_service.rss_service, 'ingest_rss_feed_with_domain')}")
    try:
        result = await rss_feed_service.update_feed_manually(feed_id)
        logger.info(f"DEBUG: Manual update result: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to manually update RSS feed: {e}")
        logger.error(f"DEBUG: Exception type: {type(e)}")
        logger.error(f"DEBUG: Exception args: {e.args}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feeds/due-for-update")
async def get_feeds_due_for_update():
    """Get feeds that are due for scheduled update"""
    try:
        feeds = await rss_feed_service.get_feeds_due_for_update()
        return {"feeds": feeds, "count": len(feeds)}
    except Exception as e:
        logger.error(f"Failed to get feeds due for update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/manual-filter")
async def manual_filter_search(request: ManualFilterRequest):
    """Manual prompt filtering for testing before creating domains"""
    try:
        all_records = await db_service.get_records(request.tenant_id, limit=1000)
        
        included_articles = []
        excluded_articles = []
        
        prompt_lower = request.prompt_description.lower()
        
        for record in all_records:
            title = record.get("data", {}).get("title", "")
            description = record.get("data", {}).get("description", "")
            content = record.get("data", {}).get("content", "")
            text_content = f"{title} {description} {content}".lower()
            
            include_score = 0
            
            if request.include_keywords:
                include_matches = sum(1 for keyword in request.include_keywords if keyword.lower() in text_content)
                include_score = include_matches / len(request.include_keywords) if request.include_keywords else 0
            else:
                relevance_keywords = []
                if "fort worth" in prompt_lower or "government" in prompt_lower or "city council" in prompt_lower or "mayor" in prompt_lower or "municipal" in prompt_lower:
                    relevance_keywords = ["fort worth", "city council", "mayor", "municipal", "government", "politics", "tarrant county"]
                elif "tech" in prompt_lower or "startup" in prompt_lower or "venture capital" in prompt_lower or "funding" in prompt_lower:
                    relevance_keywords = ["startup", "venture capital", "funding", "tech", "innovation", "entrepreneur"]
                elif "business" in prompt_lower or "local" in prompt_lower or "innovation" in prompt_lower:
                    relevance_keywords = ["business", "innovation", "local", "company"]
                elif "policy" in prompt_lower or "official" in prompt_lower or "announcement" in prompt_lower:
                    relevance_keywords = ["policy", "announcement", "official", "government"]
                
                if relevance_keywords:
                    include_matches = sum(1 for keyword in relevance_keywords if keyword in text_content)
                    include_score = include_matches / len(relevance_keywords) if relevance_keywords else 0
                else:
                    include_score = 0.1
            
            exclude_keywords = request.exclude_keywords or []
            if "fort worth" in prompt_lower or "government" in prompt_lower:
                exclude_keywords.extend(["sports", "entertainment", "celebrity", "movie"])
            elif "tech" in prompt_lower or "startup" in prompt_lower:
                exclude_keywords.extend(["sports", "politics", "celebrity"])
            elif "business" in prompt_lower:
                exclude_keywords.extend(["celebrity", "gossip", "sports"])
            elif "policy" in prompt_lower or "official" in prompt_lower:
                exclude_keywords.extend(["recipe", "movie", "horoscope", "celebrity", "sports"])
            
            exclude_penalty = sum(1 for keyword in exclude_keywords if keyword in text_content)
            
            is_included = (include_score >= request.min_include_score) and (exclude_penalty == 0)
            
            article_result = SearchResult(
                uuid=record["uuid"],
                title=title,
                description=description,
                link=record.get("data", {}).get("link", ""),
                score=include_score,
                published=record.get("data", {}).get("published")
            )
            
            if is_included:
                included_articles.append(article_result)
            else:
                excluded_articles.append(article_result)
        
        return {
            "query": request.prompt_description,
            "included_articles": included_articles[:request.limit],
            "excluded_articles": excluded_articles[:request.limit],
            "total_included": len(included_articles),
            "total_excluded": len(excluded_articles),
            "filter_settings": {
                "include_keywords": request.include_keywords,
                "exclude_keywords": exclude_keywords,
                "min_include_score": request.min_include_score
            }
        }        
    except Exception as e:
        logger.error(f"Manual filter search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/promotion/promote", response_model=PromotionResult)
async def promote_staged_records(request: PromotionRequest):
    """Promote staged records to permanent storage based on filtering criteria"""
    try:
        result = await promotion_service.promote_staged_records(
            tenant_id=request.tenant_id,
            domain_id=request.domain_id,
            promotion_threshold=request.promotion_threshold,
            max_records=request.max_records,
            dry_run=request.dry_run
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Failed to promote records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/promotion/statistics", response_model=PromotionStatistics)
async def get_promotion_statistics(tenant_id: str = "default"):
    """Get statistics about record promotion for a tenant"""
    try:
        stats = await promotion_service.get_promotion_statistics(tenant_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get promotion statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-data/load")
async def load_test_data():
    """Load synthetic test data from GitHub into the database"""
    try:
        import json
        import httpx
        from datetime import datetime
        import hashlib
        
        github_url = "https://raw.githubusercontent.com/twinfortworth/universal-db/devin/1754989671-rss-ingestion/test_dataset.json"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(github_url)
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Test data file not found on GitHub")
            
            dataset = response.json()
        
        domain_mapping = {}
        domains_data = [
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
        
        for domain_data in domains_data:
            request = CreateDomainRequest(**domain_data)
            domain = await domain_service.create_domain(request)
            domain_mapping[domain_data['name']] = domain.domain_id
        
        category_to_domain = {
            'fort_worth_political': 'Fort Worth Political',
            'tech_startups': 'Tech Startups', 
            'mixed_content': 'Mixed Content',
            'noise_heavy': 'Noise Heavy'
        }
        
        total_loaded = 0
        
        for category, articles in dataset['articles'].items():
            domain_name = category_to_domain.get(category)
            domain_id = domain_mapping.get(domain_name) if domain_name else None
            
            if not domain_id:
                continue
            
            for article in articles:
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
                        
                        total_loaded += 1
                
                except Exception as e:
                    logger.error(f"Error loading article from {category}: {e}")
        
        all_records = await db_service.get_records("default", limit=1000)
        staged_records = [r for r in all_records if r.get('schema_id') == 'staged_rss_item']
        test_records = [r for r in staged_records if r.get('data', {}).get('staging_metadata', {}).get('test_data')]
        
        by_category = {}
        for record in test_records:
            category = record.get('data', {}).get('staging_metadata', {}).get('category', 'Unknown')
            by_category[category] = by_category.get(category, 0) + 1
        
        return {
            "success": True,
            "message": f"Successfully loaded {total_loaded} test articles",
            "total_records": len(all_records),
            "staged_records": len(staged_records),
            "test_records": len(test_records),
            "by_category": by_category,
            "domain_mapping": domain_mapping
        }
        
    except Exception as e:
        logger.error(f"Failed to load test data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/promotion/cleanup")
async def cleanup_old_records(tenant_id: str = "default", max_age_days: int = 90, dry_run: bool = True):
    """Clean up old discarded records to free storage space"""
    try:
        result = await promotion_service.cleanup_old_records(tenant_id, max_age_days, dry_run)
        return result
    except Exception as e:
        logger.error(f"Failed to cleanup old records: {e}")
        raise HTTPException(status_code=500, detail=str(e))
