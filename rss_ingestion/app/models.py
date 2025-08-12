from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
import uuid as uuid_lib


class Source(BaseModel):
    origin: str = Field(..., description="The URL, file path, or API endpoint the data came from")
    type: str = Field(..., description="The type of the original source")


class UniversalWrapper(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid_lib.uuid4()), description="Unique identifier for the record")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="ISO-8601 UTC timestamp of creation")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="ISO-8601 UTC timestamp of last update")
    schema_id: str = Field(..., description="Identifier for the schema template")
    tenant_id: str = Field(default="default", description="Identifier for the tenant that owns this record")
    source: Source = Field(..., description="Source information")
    data: Dict[str, Any] = Field(..., description="The flexible, domain-specific data payload")


class RSSItem(BaseModel):
    title: str
    description: Optional[str] = None
    link: str
    published: Optional[datetime] = None
    content: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class IngestRSSRequest(BaseModel):
    feed_url: str = Field(..., description="URL of the RSS feed to ingest")
    tenant_id: str = Field(default="default", description="Tenant identifier")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    tenant_id: str = Field(default="default", description="Tenant identifier")
    limit: int = Field(default=10, description="Maximum number of results")


class SearchResult(BaseModel):
    uuid: str
    title: str
    description: Optional[str]
    link: str
    score: float
    published: Optional[datetime]


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    POLICY = "policy"
    VOTE = "vote"
    PROJECT = "project"


class DomainEntity(BaseModel):
    name: str
    type: EntityType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for entity extraction")
    context: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)


class DomainTemplate(BaseModel):
    domain_id: str = Field(..., description="Unique identifier for the domain")
    name: str = Field(..., description="Human-readable domain name")
    description: str = Field(..., description="Description of the domain")
    keywords: List[str] = Field(default_factory=list, description="Keywords to match for domain relevance")
    entities: List[str] = Field(default_factory=list, description="Known entities to track")
    locations: List[str] = Field(default_factory=list, description="Geographic locations of interest")
    exclude_keywords: List[str] = Field(default_factory=list, description="Keywords to exclude")
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum relevance score to accept")
    entity_patterns: Dict[str, List[str]] = Field(default_factory=dict, description="Regex patterns for entity recognition by type")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CreateDomainRequest(BaseModel):
    name: str = Field(..., description="Human-readable domain name")
    description: str = Field(..., description="Description of the domain")
    keywords: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0)
    entity_patterns: Dict[str, List[str]] = Field(default_factory=dict)


class EnhancedRSSItem(RSSItem):
    entities: List[DomainEntity] = Field(default_factory=list, description="Extracted domain entities")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Domain relevance score")
    domain_tags: List[str] = Field(default_factory=list, description="Domain-specific tags")
    relationships: Dict[str, List[str]] = Field(default_factory=dict, description="Entity relationships")
    sentiment: Optional[str] = Field(default=None, description="Sentiment analysis result")
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Calculated importance score")


class DomainIngestRequest(IngestRSSRequest):
    domain_id: str = Field(..., description="Domain template to use for filtering")
    extract_entities: bool = Field(default=True, description="Whether to extract entities")
    min_relevance: Optional[float] = Field(default=None, description="Override domain's min relevance score")


class EntityRecommendation(BaseModel):
    entity: DomainEntity
    reason: str = Field(..., description="Why this entity is recommended")
    source_articles: List[str] = Field(default_factory=list, description="UUIDs of articles mentioning this entity")
    frequency: int = Field(default=1, description="How often this entity appears")
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class DomainAnalytics(BaseModel):
    total_articles: int
    relevant_articles: int
    relevance_rate: float
    top_entities: List[DomainEntity]
    new_entities: List[EntityRecommendation]
    trending_topics: List[str]
    time_period: str
