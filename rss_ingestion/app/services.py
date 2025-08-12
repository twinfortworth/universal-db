import hashlib
import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
import feedparser
import httpx
from openai import OpenAI
import os
from dotenv import load_dotenv
import uuid as uuid_lib

try:
    from rank_bm25 import BM25Okapi
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from sentence_transformers import SentenceTransformer
    import torch
    RAG_DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RAG dependencies not available: {e}")
    RAG_DEPENDENCIES_AVAILABLE = False
    BM25Okapi = None
    AutoTokenizer = None
    AutoModelForSequenceClassification = None
    SentenceTransformer = None
    torch = None

from .models import (
    UniversalWrapper, RSSItem, Source, DomainTemplate, CreateDomainRequest, 
    DomainEntity, EntityType, EnhancedRSSItem, RSSFeed, CreateRSSFeedRequest, 
    UpdateRSSFeedRequest, RSSFeedListResponse, FeedUpdateResult, UpdateSchedule, 
    FeedStatus, UpdateFrequency
)

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
        self.bm25_index = None
        self.bm25_documents = []
        self.bm25_metadata = []
        
        if RAG_DEPENDENCIES_AVAILABLE:
            try:
                self.reranker_tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3")
                self.reranker_model = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-v2-m3")
                logger.info("Re-ranking model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load re-ranking model: {e}")
                self.reranker_tokenizer = None
                self.reranker_model = None
                
            try:
                self.local_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Local embedding model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load local embedding model: {e}")
                self.local_embedding_model = None
        else:
            self.reranker_tokenizer = None
            self.reranker_model = None
            self.local_embedding_model = None
        
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
            logger.info("OpenAI API key not provided - using local embeddings")

    async def init_collection(self):
        """Initialize in-memory vector storage"""
        logger.info("Using in-memory vector storage for proof of concept")
        self.vectors = {}

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI or local model"""
        try:
            if self.openai_client:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            elif self.local_embedding_model:
                logger.info("Using local embedding model")
                embedding = self.local_embedding_model.encode(text)
                return embedding.tolist()
            else:
                logger.warning("No embedding model available - returning mock embedding")
                return [0.1] * 384  # all-MiniLM-L6-v2 has 384 dimensions
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def save_vector(self, uuid: str, embedding: List[float], metadata: dict) -> bool:
        """Save vector to in-memory storage and BM25 index"""
        try:
            self.vectors[uuid] = {
                "uuid": uuid,
                "embedding": embedding,
                "metadata": metadata
            }
            
            title = metadata.get("title", "")
            description = metadata.get("description", "")
            text_content = f"{title} {description}".strip()
            
            if text_content:
                await self.add_to_bm25_index(uuid, text_content, metadata)
            
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

    def _preprocess_text(self, text: str) -> List[str]:
        """Preprocess text for BM25 indexing"""
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens

    async def add_to_bm25_index(self, uuid: str, text: str, metadata: dict):
        """Add document to BM25 index"""
        try:
            tokens = self._preprocess_text(text)
            self.bm25_documents.append(tokens)
            self.bm25_metadata.append({"uuid": uuid, "metadata": metadata})
            
            if len(self.bm25_documents) > 0 and BM25Okapi:
                self.bm25_index = BM25Okapi(self.bm25_documents)
            
            logger.info(f"Added document {uuid} to BM25 index")
        except Exception as e:
            logger.error(f"Failed to add document to BM25 index: {e}")

    async def search_bm25(self, query: str, tenant_id: str, limit: int = 10) -> List[dict]:
        """Search using BM25 keyword matching"""
        try:
            if not self.bm25_index or len(self.bm25_documents) == 0:
                return []
            
            query_tokens = self._preprocess_text(query)
            scores = self.bm25_index.get_scores(query_tokens)
            
            results = []
            for i, score in enumerate(scores):
                metadata_entry = self.bm25_metadata[i]
                if metadata_entry["metadata"].get("tenant_id") == tenant_id:
                    results.append({
                        "uuid": metadata_entry["uuid"],
                        "score": float(score),
                        "metadata": metadata_entry["metadata"]
                    })
            
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    async def hybrid_search(self, query: str, tenant_id: str, limit: int = 10, 
                          bm25_weight: float = 0.5, vector_weight: float = 0.5) -> List[dict]:
        """Hybrid search combining BM25 and vector similarity with reciprocal rank fusion"""
        try:
            query_embedding = await self.generate_embedding(query)
            vector_results = await self.search_vectors(query_embedding, tenant_id, limit * 2)
            
            bm25_results = await self.search_bm25(query, tenant_id, limit * 2)
            
            def reciprocal_rank_fusion(results_list: List[List[dict]], weights: List[float]) -> List[dict]:
                rrf_scores = {}
                
                for results, weight in zip(results_list, weights):
                    for rank, result in enumerate(results):
                        uuid = result["uuid"]
                        rrf_score = weight / (rank + 60)
                        
                        if uuid in rrf_scores:
                            rrf_scores[uuid]["rrf_score"] += rrf_score
                        else:
                            rrf_scores[uuid] = {
                                "uuid": uuid,
                                "metadata": result["metadata"],
                                "rrf_score": rrf_score,
                                "vector_score": 0.0,
                                "bm25_score": 0.0
                            }
                
                for result in vector_results:
                    if result["uuid"] in rrf_scores:
                        rrf_scores[result["uuid"]]["vector_score"] = result["score"]
                
                for result in bm25_results:
                    if result["uuid"] in rrf_scores:
                        rrf_scores[result["uuid"]]["bm25_score"] = result["score"]
                
                final_results = list(rrf_scores.values())
                final_results.sort(key=lambda x: x["rrf_score"], reverse=True)
                return final_results[:limit]
            
            return reciprocal_rank_fusion([vector_results, bm25_results], [vector_weight, bm25_weight])
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []

    async def rerank_results(self, query: str, results: List[dict], top_n: int = 5) -> List[dict]:
        """Re-rank search results using cross-encoder model"""
        try:
            if len(results) == 0 or not self.reranker_model or not self.reranker_tokenizer:
                return results[:top_n]
            
            pairs = []
            for result in results:
                title = result["metadata"].get("title", "")
                description = result["metadata"].get("description", "")
                doc_text = f"{title} {description}".strip()
                pairs.append([query, doc_text])
            
            inputs = self.reranker_tokenizer(pairs, padding=True, truncation=True, 
                                          return_tensors="pt", max_length=512)
            
            with torch.no_grad():
                outputs = self.reranker_model(**inputs)
                scores = torch.nn.functional.softmax(outputs.logits, dim=-1)[:, 1].cpu().numpy()
            
            for i, result in enumerate(results):
                result["rerank_score"] = float(scores[i])
            
            results.sort(key=lambda x: x["rerank_score"], reverse=True)
            return results[:top_n]
            
        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            return results[:top_n]


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

    async def _generate_contextual_embedding_text(self, rss_item: RSSItem, domain_id: Optional[str] = None) -> str:
        """Generate contextual embedding text for RSS item"""
        try:
            base_text = f"{rss_item.title} {rss_item.description or ''} {rss_item.content or ''}"
            
            if not domain_id:
                return base_text
            
            domain = await self.domain_service.get_domain(domain_id)
            if not domain:
                return base_text
            
            context_prompt = f"""You are an AI assistant specializing in content analysis.
Your task is to provide brief, relevant context for this RSS article
based on the domain: {domain.name}.

Domain Description: {domain.description}
Domain Keywords: {', '.join(domain.keywords)}
Domain Locations: {', '.join(domain.locations)}

Here is the RSS article:
Title: {rss_item.title}
Content: {base_text[:2000]}

Provide a concise context (2-3 sentences max) for this article,
focusing on its relevance to the {domain.name} domain.
Answer only with the context and nothing else.
Context should start with 'This article focuses on...'

Context:"""
            
            if self.vector_service.openai_client:
                response = self.vector_service.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": context_prompt}],
                    max_tokens=150,
                    temperature=0
                )
                context = response.choices[0].message.content.strip()
                return f"{context}\n\n{base_text}"
            
            return base_text
            
        except Exception as e:
            logger.error(f"Failed to generate contextual embedding text: {e}")
            return f"{rss_item.title} {rss_item.description or ''} {rss_item.content or ''}"

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
                    
                    rss_data = rss_item.model_dump()
                    if hasattr(self, 'current_domain_id') and self.current_domain_id:
                        rss_data['staging_metadata'] = {
                            'domain_id': self.current_domain_id,
                            'requires_domain_filtering': True,
                            'ingestion_timestamp': datetime.utcnow().isoformat()
                        }
                    else:
                        rss_data['staging_metadata'] = {
                            'requires_domain_filtering': False,
                            'ingestion_timestamp': datetime.utcnow().isoformat()
                        }
                    
                    wrapper = UniversalWrapper(
                        schema_id="staged_rss_item",
                        tenant_id=tenant_id,
                        source=Source(origin=feed_url, type="rss"),
                        data=rss_data
                    )
                    
                    saved = await self.db_service.save_record(wrapper, content_hash)
                    
                    if saved:
                        embedding_text = f"{rss_item.title} {rss_item.description or ''} {rss_item.content or ''}"
                        embedding = await self.vector_service.generate_embedding(embedding_text)
                        
                        if embedding:
                            metadata = {
                                "tenant_id": tenant_id,
                                "schema_id": "staged_rss_item",
                                "title": rss_item.title,
                                "link": rss_item.link,
                                "published": rss_item.published.isoformat() if rss_item.published else None,
                                "domain_id": getattr(self, 'current_domain_id', None),
                                "requires_filtering": rss_data['staging_metadata']['requires_domain_filtering']
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

    # async def ingest_rss_feed_with_domain(self, feed_url: str, tenant_id: str, domain_id: str, 
    #                                     extract_entities: bool = True, min_relevance: Optional[float] = None) -> dict:


class RSSFeedService:
    def __init__(self, db_service: DatabaseService, rss_service: RSSService, domain_service: DomainService):
        self.db_service = db_service
        self.rss_service = rss_service
        self.domain_service = domain_service
        self.feeds: Dict[str, RSSFeed] = {}
        
    async def create_feed(self, request: CreateRSSFeedRequest) -> RSSFeed:
        feed = RSSFeed(
            name=request.name,
            url=request.url,
            domain_id=request.domain_id,
            tenant_id=request.tenant_id,
            is_active=request.is_active,
            schedule=request.schedule,
            status=FeedStatus.PENDING
        )
        
        feed.schedule.next_update = self._calculate_next_update(feed.schedule)
        
        self.feeds[feed.feed_id] = feed
        logger.info(f"Created RSS feed: {feed.name} ({feed.feed_id})")
        return feed
    
    async def get_feed(self, feed_id: str) -> Optional[RSSFeed]:
        return self.feeds.get(feed_id)
    
    async def list_feeds(self, tenant_id: str = "default", page: int = 1, page_size: int = 10) -> RSSFeedListResponse:
        tenant_feeds = [feed for feed in self.feeds.values() if feed.tenant_id == tenant_id]
        total = len(tenant_feeds)
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        feeds = tenant_feeds[start_idx:end_idx]
        
        return RSSFeedListResponse(
            feeds=feeds,
            total=total,
            page=page,
            page_size=page_size
        )
    
    async def update_feed(self, feed_id: str, request: UpdateRSSFeedRequest) -> Optional[RSSFeed]:
        feed = self.feeds.get(feed_id)
        if not feed:
            return None
        
        if request.name is not None:
            feed.name = request.name
        if request.url is not None:
            feed.url = request.url
        if request.domain_id is not None:
            feed.domain_id = request.domain_id
        if request.is_active is not None:
            feed.is_active = request.is_active
        if request.schedule is not None:
            feed.schedule = request.schedule
            feed.schedule.next_update = self._calculate_next_update(feed.schedule)
        
        feed.updated_at = datetime.utcnow()
        logger.info(f"Updated RSS feed: {feed.name} ({feed.feed_id})")
        return feed
    
    async def delete_feed(self, feed_id: str) -> bool:
        if feed_id in self.feeds:
            feed = self.feeds[feed_id]
            del self.feeds[feed_id]
            logger.info(f"Deleted RSS feed: {feed.name} ({feed_id})")
            return True
        return False
    
    async def toggle_feed_status(self, feed_id: str) -> Optional[RSSFeed]:
        feed = self.feeds.get(feed_id)
        if not feed:
            return None
        
        feed.is_active = not feed.is_active
        feed.updated_at = datetime.utcnow()
        logger.info(f"Toggled RSS feed status: {feed.name} ({feed.feed_id}) -> {'active' if feed.is_active else 'inactive'}")
        return feed
    
    async def update_feed_manually(self, feed_id: str) -> FeedUpdateResult:
        feed = self.feeds.get(feed_id)
        if not feed:
            return FeedUpdateResult(
                feed_id=feed_id,
                success=False,
                articles_processed=0,
                articles_filtered=0,
                error_message="Feed not found"
            )
        
        if not feed.is_active:
            return FeedUpdateResult(
                feed_id=feed_id,
                success=False,
                articles_processed=0,
                articles_filtered=0,
                error_message="Feed is inactive"
            )
        
        try:
            feed.status = FeedStatus.PENDING
            
            logger.info(f"DEBUG: RSS service type: {type(self.rss_service)}")
            logger.info(f"DEBUG: RSS service methods: {dir(self.rss_service)}")
            
            if feed.domain_id:
                self.rss_service.current_domain_id = feed.domain_id
                logger.info(f"DEBUG: Calling ingest_rss_feed for feed {feed_id} with domain context {feed.domain_id}")
            else:
                self.rss_service.current_domain_id = None
                logger.info(f"DEBUG: Calling ingest_rss_feed for feed {feed_id}")
            
            result = await self.rss_service.ingest_rss_feed(feed.url, feed.tenant_id)
            
            if "error" in result:
                feed.status = FeedStatus.ERROR
                feed.last_error = result["error"]
                feed.failed_updates += 1
                
                return FeedUpdateResult(
                    feed_id=feed_id,
                    success=False,
                    articles_processed=0,
                    articles_filtered=0,
                    error_message=result["error"]
                )
            else:
                feed.status = FeedStatus.ACTIVE
                feed.last_update = datetime.utcnow()
                feed.last_error = None
                feed.successful_updates += 1
                feed.total_articles += result.get("processed_items", 0)
                
                feed.schedule.next_update = self._calculate_next_update(feed.schedule)
                
                return FeedUpdateResult(
                    feed_id=feed_id,
                    success=True,
                    articles_processed=result.get("processed_items", 0),
                    articles_filtered=result.get("filtered_out", 0)
                )
                
        except Exception as e:
            error_msg = f"Failed to update RSS feed: {e}"
            logger.error(error_msg)
            
            feed.status = FeedStatus.ERROR
            feed.last_error = error_msg
            feed.failed_updates += 1
            
            return FeedUpdateResult(
                feed_id=feed_id,
                success=False,
                articles_processed=0,
                articles_filtered=0,
                error_message=error_msg
            )
    
    async def get_feeds_due_for_update(self) -> List[RSSFeed]:
        now = datetime.utcnow()
        due_feeds = []
        
        for feed in self.feeds.values():
            if (feed.is_active and 
                feed.schedule.next_update and 
                feed.schedule.next_update <= now):
                due_feeds.append(feed)
        
        return due_feeds
    
    def _calculate_next_update(self, schedule: UpdateSchedule) -> datetime:
        from datetime import timedelta
        
        now = datetime.utcnow()
        
        if schedule.frequency == UpdateFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif schedule.frequency == UpdateFrequency.DAILY:
            next_update = now + timedelta(days=1)
            if schedule.time_of_day:
                try:
                    hour, minute = map(int, schedule.time_of_day.split(':'))
                    next_update = next_update.replace(hour=hour, minute=minute, second=0, microsecond=0)
                except:
                    pass
            return next_update
        elif schedule.frequency == UpdateFrequency.WEEKLY:
            days_ahead = 7
            if schedule.day_of_week is not None:
                days_ahead = (schedule.day_of_week - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
            next_update = now + timedelta(days=days_ahead)
            if schedule.time_of_day:
                try:
                    hour, minute = map(int, schedule.time_of_day.split(':'))
                    next_update = next_update.replace(hour=hour, minute=minute, second=0, microsecond=0)
                except:
                    pass
            return next_update
        elif schedule.frequency == UpdateFrequency.MONTHLY:
            next_update = now + timedelta(days=30)
            if schedule.day_of_month:
                try:
                    next_update = next_update.replace(day=schedule.day_of_month)
                except:
                    pass
            if schedule.time_of_day:
                try:
                    hour, minute = map(int, schedule.time_of_day.split(':'))
                    next_update = next_update.replace(hour=hour, minute=minute, second=0, microsecond=0)
                except:
                    pass
            return next_update
        
        return now + timedelta(days=1)
