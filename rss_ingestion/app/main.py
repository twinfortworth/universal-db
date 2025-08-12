from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from .models import IngestRSSRequest, SearchRequest, SearchResult
from .services import DatabaseService, VectorService, RSSService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_service = DatabaseService()
vector_service = VectorService()
rss_service = RSSService(db_service, vector_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing databases...")
    await db_service.init_db()
    await vector_service.init_collection()
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
