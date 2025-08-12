from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from .models import (
    IngestRSSRequest, SearchRequest, SearchResult, CreateDomainRequest, 
    DomainIngestRequest, DomainAnalytics, DomainEntity, EntityType,
    CreateRSSFeedRequest, UpdateRSSFeedRequest, RSSFeedListResponse, FeedUpdateResult, RSSFeed
)
from .services import DatabaseService, VectorService, RSSService, DomainService, RSSFeedService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_service = DatabaseService()
vector_service = VectorService()
domain_service = DomainService()
rss_service = RSSService(db_service, vector_service, domain_service)
rss_feed_service = RSSFeedService(db_service, rss_service, domain_service)


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


@app.post("/search/domain")
async def domain_filtered_search(request: SearchRequest):
    """Domain-specific search with relevance filtering"""
    try:
        if not request.domain_id:
            raise HTTPException(status_code=400, detail="domain_id is required for domain search")
        
        domain = await domain_service.get_domain(request.domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        
        hybrid_results = await vector_service.hybrid_search(
            request.query, request.tenant_id, request.limit * 3,
            request.bm25_weight, request.vector_weight
        )
        
        domain_filtered_results = []
        for result in hybrid_results:
            metadata = result["metadata"]
            if metadata.get("domain_id") == request.domain_id:
                title = metadata.get("title", "")
                description = metadata.get("description", "")
                text_content = f"{title} {description}"
                relevance_score = domain_service.calculate_relevance_score(text_content, domain)
                
                if relevance_score >= domain.min_relevance_score:
                    result["domain_relevance_score"] = relevance_score
                    domain_filtered_results.append(result)
        
        if request.use_reranking:
            reranked_results = await vector_service.rerank_results(
                request.query, domain_filtered_results, request.limit
            )
        else:
            reranked_results = domain_filtered_results[:request.limit]
        
        search_results = []
        for result in reranked_results:
            metadata = result["metadata"]
            search_results.append(SearchResult(
                uuid=result["uuid"],
                title=metadata.get("title", ""),
                description=metadata.get("description"),
                link=metadata.get("link", ""),
                score=result.get("rerank_score", result.get("domain_relevance_score", 0.0)),
                published=metadata.get("published")
            ))
        
        return {
            "query": request.query,
            "domain_id": request.domain_id,
            "search_type": "domain_filtered_hybrid",
            "results": search_results,
            "count": len(search_results)
        }
    except Exception as e:
        logger.error(f"Domain filtered search failed: {e}")
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
