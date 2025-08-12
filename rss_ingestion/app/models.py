from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
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
