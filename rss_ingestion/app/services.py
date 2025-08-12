import hashlib
import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
import feedparser
import httpx
from openai import OpenAI
from .models import UniversalWrapper, RSSItem, Source, DomainTemplate, CreateDomainRequest, DomainEntity, EntityType, EnhancedRSSItem
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


class DomainService:
    def __init__(self):
        self.domains: Dict[str, DomainTemplate] = {}
        self._init_default_domains()
    
    def _init_default_domains(self):
        fort_worth_domain = DomainTemplate(
            domain_id="fort_worth_political",
            name="Fort Worth Political",
            description="Fort Worth city politics, government, and civic affairs",
            keywords=[
                "fort worth", "tarrant county", "city council", "mayor", "city manager",
                "municipal", "ordinance", "zoning", "budget", "tax", "bond", "election",
                "public hearing", "agenda", "vote", "resolution", "development",
                "transportation", "infrastructure", "police", "fire department",
                "parks", "library", "water", "utilities", "downtown"
            ],
            entities=[
                "Mattie Parker", "City of Fort Worth", "Tarrant County", "Fort Worth City Council",
                "Fort Worth ISD", "Trinity Metro", "DFW Airport", "Alliance Airport"
            ],
            locations=[
                "Fort Worth", "Tarrant County", "Texas", "DFW", "Alliance", "Downtown Fort Worth",
                "Cultural District", "Stockyards", "Trinity River"
            ],
            entity_patterns={
                "person": [r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"],
                "organization": [r"\b(?:City of|County of|Department of) [A-Z][a-z ]+\b"],
                "location": [r"\b(?:Fort Worth|Tarrant County|Texas|DFW)\b"]
            }
        )
        self.domains[fort_worth_domain.domain_id] = fort_worth_domain
    
    async def create_domain(self, request: CreateDomainRequest) -> DomainTemplate:
        domain_id = request.name.lower().replace(" ", "_").replace("-", "_")
        domain = DomainTemplate(
            domain_id=domain_id,
            name=request.name,
            description=request.description,
            keywords=request.keywords,
            entities=request.entities,
            locations=request.locations,
            exclude_keywords=request.exclude_keywords,
            min_relevance_score=request.min_relevance_score,
            entity_patterns=request.entity_patterns
        )
        self.domains[domain_id] = domain
        return domain
    
    async def get_domain(self, domain_id: str) -> Optional[DomainTemplate]:
        return self.domains.get(domain_id)
    
    async def list_domains(self) -> List[DomainTemplate]:
        return list(self.domains.values())
    
    async def update_domain(self, domain_id: str, updates: Dict[str, Any]) -> Optional[DomainTemplate]:
        if domain_id not in self.domains:
            return None
        domain = self.domains[domain_id]
        for key, value in updates.items():
            if hasattr(domain, key):
                setattr(domain, key, value)
        domain.updated_at = datetime.utcnow()
        return domain
    
    def extract_entities(self, text: str, domain: DomainTemplate) -> List[DomainEntity]:
        entities = []
        
        for entity_type, patterns in domain.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity_name = match.group().strip()
                    if entity_name and len(entity_name) > 2:
                        entities.append(DomainEntity(
                            name=entity_name,
                            type=EntityType(entity_type),
                            confidence=0.8,
                            context=text[max(0, match.start()-50):match.end()+50]
                        ))
        
        for known_entity in domain.entities:
            if known_entity.lower() in text.lower():
                entities.append(DomainEntity(
                    name=known_entity,
                    type=EntityType.ORGANIZATION,
                    confidence=0.9,
                    context=text
                ))
        
        return entities
    
    def calculate_relevance_score(self, text: str, domain: DomainTemplate) -> float:
        text_lower = text.lower()
        score = 0.0
        
        keyword_matches = sum(1 for keyword in domain.keywords if keyword.lower() in text_lower)
        keyword_score = min(keyword_matches / max(len(domain.keywords), 1), 1.0) * 0.6
        
        location_matches = sum(1 for location in domain.locations if location.lower() in text_lower)
        location_score = min(location_matches / max(len(domain.locations), 1), 1.0) * 0.2
        
        entity_matches = sum(1 for entity in domain.entities if entity.lower() in text_lower)
        entity_score = min(entity_matches / max(len(domain.entities), 1), 1.0) * 0.2
        
        exclude_penalty = sum(0.1 for exclude in domain.exclude_keywords if exclude.lower() in text_lower)
        
        score = keyword_score + location_score + entity_score - exclude_penalty
        return max(0.0, min(1.0, score))


class RSSService:
    def __init__(self, db_service: DatabaseService, vector_service: VectorService, domain_service: DomainService):
        self.db_service = db_service
        self.vector_service = vector_service
        self.domain_service = domain_service

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

    async def ingest_rss_feed_with_domain(self, feed_url: str, tenant_id: str, domain_id: str, 
                                        extract_entities: bool = True, min_relevance: Optional[float] = None) -> dict:
        domain = await self.domain_service.get_domain(domain_id)
        if not domain:
            return {"error": f"Domain {domain_id} not found"}
        
        min_score = min_relevance if min_relevance is not None else domain.min_relevance_score
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(feed_url)
                response.raise_for_status()
                
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"RSS feed parsing had issues: {feed.bozo_exception}")

            results = {
                "feed_url": feed_url,
                "domain_id": domain_id,
                "domain_name": domain.name,
                "feed_title": getattr(feed.feed, 'title', 'Unknown'),
                "total_items": len(feed.entries),
                "processed_items": 0,
                "filtered_out": 0,
                "skipped_duplicates": 0,
                "errors": []
            }

            for entry in feed.entries:
                try:
                    rss_item = self._parse_rss_item(entry)
                    
                    full_text = f"{rss_item.title} {rss_item.description or ''} {rss_item.content or ''}"
                    relevance_score = self.domain_service.calculate_relevance_score(full_text, domain)
                    
                    if relevance_score < min_score:
                        results["filtered_out"] += 1
                        continue
                    
                    entities = []
                    if extract_entities:
                        entities = self.domain_service.extract_entities(full_text, domain)
                    
                    enhanced_item = EnhancedRSSItem(
                        **rss_item.model_dump(),
                        entities=entities,
                        relevance_score=relevance_score,
                        domain_tags=[domain.name],
                        importance_score=relevance_score
                    )
                    
                    content_for_hash = f"{rss_item.title}{rss_item.link}{rss_item.content}"
                    content_hash = self._generate_content_hash(content_for_hash)
                    
                    wrapper = UniversalWrapper(
                        schema_id="enhanced_rss_item",
                        tenant_id=tenant_id,
                        source=Source(origin=feed_url, type="rss"),
                        data=enhanced_item.model_dump()
                    )
                    
                    saved = await self.db_service.save_record(wrapper, content_hash)
                    
                    if saved:
                        embedding_text = f"Domain: {domain.name}. {full_text}"
                        embedding = await self.vector_service.generate_embedding(embedding_text)
                        
                        if embedding:
                            metadata = {
                                "tenant_id": tenant_id,
                                "domain_id": domain_id,
                                "schema_id": "enhanced_rss_item",
                                "title": rss_item.title,
                                "link": rss_item.link,
                                "relevance_score": relevance_score,
                                "entity_count": len(entities),
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
