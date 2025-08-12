import hashlib
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import feedparser
import httpx
from openai import OpenAI
from .models import UniversalWrapper, RSSItem, Source
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self):
        self.records: Dict[str, dict] = {}
        self.content_hashes: set = set()
        
    async def init_db(self):
        """Initialize in-memory database"""
        logger.info("Using in-memory database for proof of concept")
        self.records = {}
        self.content_hashes = set()

    async def save_record(self, wrapper: UniversalWrapper, content_hash: str) -> bool:
        """Save a record to in-memory storage"""
        try:
            if content_hash in self.content_hashes:
                return False
            
            self.content_hashes.add(content_hash)
            self.records[wrapper.uuid] = {
                "uuid": wrapper.uuid,
                "created_at": wrapper.created_at,
                "updated_at": wrapper.updated_at,
                "schema_id": wrapper.schema_id,
                "tenant_id": wrapper.tenant_id,
                "source": wrapper.source.model_dump(),
                "data": wrapper.data,
                "content_hash": content_hash
            }
            return True
        except Exception as e:
            logger.error(f"Failed to save record: {e}")
            return False

    async def get_records(self, tenant_id: str, limit: int = 10, offset: int = 0) -> List[dict]:
        """Get records from in-memory storage"""
        try:
            tenant_records = [
                record for record in self.records.values() 
                if record["tenant_id"] == tenant_id
            ]
            
            tenant_records.sort(key=lambda x: x["created_at"], reverse=True)
            
            start_idx = offset
            end_idx = offset + limit
            return tenant_records[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Failed to get records: {e}")
            return []


class VectorService:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.vectors: Dict[str, dict] = {}
        
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
            logger.warning("OpenAI API key not provided - embeddings will be disabled")

    async def init_collection(self):
        """Initialize in-memory vector storage"""
        logger.info("Using in-memory vector storage for proof of concept")
        self.vectors = {}

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI"""
        if not self.openai_client:
            logger.warning("OpenAI client not available - returning mock embedding")
            return [0.1] * 1536
            
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.1] * 1536

    async def save_vector(self, uuid: str, embedding: List[float], metadata: dict) -> bool:
        """Save vector to in-memory storage"""
        try:
            self.vectors[uuid] = {
                "uuid": uuid,
                "embedding": embedding,
                "metadata": metadata
            }
            return True
        except Exception as e:
            logger.error(f"Failed to save vector: {e}")
            return False

    async def search_vectors(self, query_embedding: List[float], tenant_id: str, limit: int = 10) -> List[dict]:
        """Search vectors using simple cosine similarity"""
        try:
            def cosine_similarity(a: List[float], b: List[float]) -> float:
                dot_product = sum(x * y for x, y in zip(a, b))
                magnitude_a = sum(x * x for x in a) ** 0.5
                magnitude_b = sum(x * x for x in b) ** 0.5
                if magnitude_a == 0 or magnitude_b == 0:
                    return 0
                return dot_product / (magnitude_a * magnitude_b)
            
            results = []
            for vector_data in self.vectors.values():
                metadata = vector_data["metadata"]
                if metadata.get("tenant_id") == tenant_id:
                    similarity = cosine_similarity(query_embedding, vector_data["embedding"])
                    results.append({
                        "uuid": vector_data["uuid"],
                        "score": similarity,
                        "metadata": metadata
                    })
            
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"Failed to search vectors: {e}")
            return []


class RSSService:
    def __init__(self, db_service: DatabaseService, vector_service: VectorService):
        self.db_service = db_service
        self.vector_service = vector_service

    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content for deduplication"""
        return hashlib.sha256(content.encode()).hexdigest()

    def _parse_rss_item(self, entry) -> RSSItem:
        """Parse a single RSS entry into RSSItem"""
        published = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6])
            except:
                pass

        content = ""
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].value if isinstance(entry.content, list) else entry.content
        elif hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'description'):
            content = entry.description

        tags = []
        if hasattr(entry, 'tags') and entry.tags:
            tags = [tag.term for tag in entry.tags if hasattr(tag, 'term')]

        return RSSItem(
            title=getattr(entry, 'title', ''),
            description=getattr(entry, 'summary', None),
            link=getattr(entry, 'link', ''),
            published=published,
            content=content,
            author=getattr(entry, 'author', None),
            tags=tags
        )

    async def ingest_rss_feed(self, feed_url: str, tenant_id: str) -> dict:
        """Ingest an RSS feed and store items in universal wrapper format"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(feed_url)
                response.raise_for_status()
                
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"RSS feed parsing had issues: {feed.bozo_exception}")

            results = {
                "feed_url": feed_url,
                "feed_title": getattr(feed.feed, 'title', 'Unknown'),
                "total_items": len(feed.entries),
                "processed_items": 0,
                "skipped_duplicates": 0,
                "errors": []
            }

            for entry in feed.entries:
                try:
                    rss_item = self._parse_rss_item(entry)
                    
                    content_for_hash = f"{rss_item.title}{rss_item.link}{rss_item.content}"
                    content_hash = self._generate_content_hash(content_for_hash)
                    
                    wrapper = UniversalWrapper(
                        schema_id="rss_item",
                        tenant_id=tenant_id,
                        source=Source(origin=feed_url, type="rss"),
                        data=rss_item.model_dump()
                    )
                    
                    saved = await self.db_service.save_record(wrapper, content_hash)
                    
                    if saved:
                        embedding_text = f"{rss_item.title} {rss_item.description or ''} {rss_item.content or ''}"
                        embedding = await self.vector_service.generate_embedding(embedding_text)
                        
                        if embedding:
                            metadata = {
                                "tenant_id": tenant_id,
                                "schema_id": "rss_item",
                                "title": rss_item.title,
                                "link": rss_item.link,
                                "published": rss_item.published.isoformat() if rss_item.published else None
                            }
                            await self.vector_service.save_vector(wrapper.uuid, embedding, metadata)
                        
                        results["processed_items"] += 1
                    else:
                        results["skipped_duplicates"] += 1
                        
                except Exception as e:
                    error_msg = f"Failed to process RSS item: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

            return results
            
        except Exception as e:
            error_msg = f"Failed to ingest RSS feed: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
