# Universal Database - RSS Ingestion System

A universal database system starting with RSS feed ingestion, implementing a simplified version of the Simplake Universal Data Standard.

## Overview

This project implements the first component of a universal database system that can ingest, store, and search data from various sources using a unified wrapper format. RSS feeds serve as the initial data source to demonstrate the core concepts.

## Features

- **Universal Wrapper Format**: Simplified schema with core fields (uuid, timestamps, schema_id, tenant_id, source, data)
- **RSS Feed Ingestion**: Parse and store RSS feed items using feedparser
- **Dual Storage Architecture**: In-memory JSON storage + vector embeddings for proof of concept
- **Content Deduplication**: SHA-256 hash-based duplicate detection
- **Semantic Search**: Vector similarity search with OpenAI embeddings (falls back to mock embeddings)
- **Multi-tenant Support**: Tenant isolation for data and search

## API Endpoints

### Health Check
```bash
GET /healthz
```

### RSS Ingestion
```bash
POST /ingest/rss
Content-Type: application/json

{
  "feed_url": "https://feeds.bbci.co.uk/news/rss.xml",
  "tenant_id": "default"
}
```

### Retrieve Records
```bash
GET /records?tenant_id=default&limit=10&offset=0
```

### Search Records
```bash
POST /search
Content-Type: application/json

{
  "query": "technology news",
  "tenant_id": "default",
  "limit": 10
}
```

## Universal Wrapper Schema

Each ingested item is wrapped in a universal format:

```json
{
  "uuid": "unique-identifier",
  "created_at": "2025-08-12T09:15:58.584775",
  "updated_at": "2025-08-12T09:15:58.584779", 
  "schema_id": "rss_item",
  "tenant_id": "default",
  "source": {
    "origin": "https://feeds.bbci.co.uk/news/rss.xml",
    "type": "rss"
  },
  "data": {
    "title": "Article Title",
    "description": "Article description",
    "link": "https://example.com/article",
    "published": "2025-08-12T05:22:14",
    "content": "Full article content",
    "author": "Author Name",
    "tags": ["tag1", "tag2"]
  }
}
```

## Technology Stack

- **FastAPI**: REST API framework
- **feedparser**: RSS feed parsing
- **OpenAI**: Text embeddings for semantic search
- **In-memory storage**: Proof of concept (PostgreSQL + Qdrant for production)
- **Python 3.12**: Runtime environment

## Getting Started

1. **Install dependencies**:
   ```bash
   poetry install
   ```

2. **Set up environment variables** (optional):
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key for real embeddings
   ```

3. **Start the development server**:
   ```bash
   poetry run fastapi dev app/main.py
   ```

4. **Test RSS ingestion**:
   ```bash
   curl -X POST "http://localhost:8000/ingest/rss" \
     -H "Content-Type: application/json" \
     -d '{"feed_url": "https://feeds.bbci.co.uk/news/rss.xml", "tenant_id": "test"}'
   ```

## Architecture

This implementation follows a simplified approach to the universal database concept:

- **Universal Wrapper**: Consistent metadata structure across all data sources
- **Schema Registry**: Simple mapping of schema_id to data structure
- **Dual Storage**: JSON for structured queries, vectors for semantic search
- **Source Tracking**: Maintain lineage and origin information
- **Tenant Isolation**: Multi-tenancy support for future scaling

## Future Enhancements

- Replace in-memory storage with PostgreSQL + Qdrant
- Add more data source types (CSV, JSON, APIs)
- Implement schema evolution and versioning
- Add governance and access control layers
- Build universal app generator based on schemas

## Testing

The system has been tested with:
- BBC News RSS feed (33 items processed successfully)
- Health check endpoint
- Record retrieval with pagination
- Semantic search functionality

All endpoints return proper HTTP status codes and JSON responses.
