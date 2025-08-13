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
    search_type: str = Field(default="vector", description="Search type: vector, bm25, hybrid")
    bm25_weight: float = Field(default=0.5, description="Weight for BM25 in hybrid search")
    vector_weight: float = Field(default=0.5, description="Weight for vector search in hybrid search")
    use_reranking: bool = Field(default=True, description="Whether to apply re-ranking")
    domain_id: Optional[str] = Field(default=None, description="Domain ID for domain-specific search")


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
    ai_prompt: str = Field(default="", description="AI prompt for filtering and defining data objects")
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
    ai_prompt: str = Field(default="", description="AI prompt for filtering and defining data objects")
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


class UpdateFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class FeedStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class UpdateSchedule(BaseModel):
    frequency: UpdateFrequency = Field(..., description="How often to update the feed")
    time_of_day: Optional[str] = Field(default=None, description="Time of day to update (HH:MM format)")
    day_of_week: Optional[int] = Field(default=None, description="Day of week for weekly updates (0=Monday)")
    day_of_month: Optional[int] = Field(default=None, description="Day of month for monthly updates")
    next_update: Optional[datetime] = Field(default=None, description="Next scheduled update time")


class RSSFeed(BaseModel):
    feed_id: str = Field(default_factory=lambda: str(uuid_lib.uuid4()), description="Unique identifier for the RSS feed")
    name: str = Field(..., description="Human-readable name for the feed")
    url: str = Field(..., description="RSS feed URL")
    domain_id: Optional[str] = Field(default=None, description="Associated domain for filtering")
    tenant_id: str = Field(default="default", description="Tenant identifier")
    is_active: bool = Field(default=True, description="Whether the feed is active")
    status: FeedStatus = Field(default=FeedStatus.PENDING, description="Current status of the feed")
    schedule: UpdateSchedule = Field(..., description="Update schedule configuration")
    last_update: Optional[datetime] = Field(default=None, description="Last successful update time")
    last_error: Optional[str] = Field(default=None, description="Last error message if any")
    total_articles: int = Field(default=0, description="Total articles ingested from this feed")
    successful_updates: int = Field(default=0, description="Number of successful updates")
    failed_updates: int = Field(default=0, description="Number of failed updates")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CreateRSSFeedRequest(BaseModel):
    name: str = Field(..., description="Human-readable name for the feed")
    url: str = Field(..., description="RSS feed URL")
    domain_id: Optional[str] = Field(default=None, description="Associated domain for filtering")
    tenant_id: str = Field(default="default", description="Tenant identifier")
    is_active: bool = Field(default=True, description="Whether the feed should be active")
    schedule: UpdateSchedule = Field(..., description="Update schedule configuration")


class UpdateRSSFeedRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="Human-readable name for the feed")
    url: Optional[str] = Field(default=None, description="RSS feed URL")
    domain_id: Optional[str] = Field(default=None, description="Associated domain for filtering")
    is_active: Optional[bool] = Field(default=None, description="Whether the feed should be active")
    schedule: Optional[UpdateSchedule] = Field(default=None, description="Update schedule configuration")


class RSSFeedListResponse(BaseModel):
    feeds: List[RSSFeed]
    total: int
    page: int
    page_size: int


class FeedUpdateResult(BaseModel):
    feed_id: str
    success: bool
    articles_processed: int
    articles_filtered: int
    error_message: Optional[str] = None
    update_time: datetime = Field(default_factory=datetime.utcnow)
