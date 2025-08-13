"""
Record Promotion Service for Universal Database

Handles promotion of records from staging to permanent storage based on
filtering criteria and relevance scores.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from .models import UniversalWrapper, DomainTemplate, Source
from .services import DatabaseService, DomainService, VectorService

logger = logging.getLogger(__name__)


class PromotionResult:
    """Result of a promotion operation"""
    
    def __init__(self):
        self.total_evaluated = 0
        self.promoted = 0
        self.discarded = 0
        self.errors = 0
        self.promoted_records = []
        self.discarded_records = []
        self.error_messages = []
        self.processing_time = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_evaluated': self.total_evaluated,
            'promoted': self.promoted,
            'discarded': self.discarded,
            'errors': self.errors,
            'promotion_rate': self.promoted / self.total_evaluated if self.total_evaluated > 0 else 0,
            'discard_rate': self.discarded / self.total_evaluated if self.total_evaluated > 0 else 0,
            'error_rate': self.errors / self.total_evaluated if self.total_evaluated > 0 else 0,
            'processing_time': self.processing_time,
            'avg_processing_time_per_record': self.processing_time / self.total_evaluated if self.total_evaluated > 0 else 0,
            'promoted_records': self.promoted_records,
            'discarded_records': self.discarded_records,
            'error_messages': self.error_messages
        }


class RecordPromotionService:
    """Service for promoting staged records to permanent storage"""
    
    def __init__(self, db_service: DatabaseService, domain_service: DomainService, vector_service: VectorService):
        self.db_service = db_service
        self.domain_service = domain_service
        self.vector_service = vector_service
        
        self.default_promotion_threshold = 0.3
        self.batch_size = 100
        self.max_age_days = 30
    
    async def promote_staged_records(self, 
                                   tenant_id: str = "default",
                                   domain_id: Optional[str] = None,
                                   promotion_threshold: Optional[float] = None,
                                   max_records: Optional[int] = None,
                                   dry_run: bool = False) -> PromotionResult:
        """
        Promote staged records to permanent storage based on filtering criteria
        
        Args:
            tenant_id: Tenant to process records for
            domain_id: Specific domain to process (None for all domains)
            promotion_threshold: Custom threshold for promotion (None for default)
            max_records: Maximum number of records to process (None for all)
            dry_run: If True, only evaluate without making changes
        
        Returns:
            PromotionResult with statistics and details
        """
        
        start_time = datetime.utcnow()
        result = PromotionResult()
        
        try:
            logger.info(f"Starting record promotion for tenant {tenant_id}")
            
            staged_records = await self._get_staged_records(tenant_id, domain_id, max_records)
            result.total_evaluated = len(staged_records)
            
            if not staged_records:
                logger.info("No staged records found for promotion")
                return result
            
            logger.info(f"Found {len(staged_records)} staged records to evaluate")
            
            batch_count = 0
            for i in range(0, len(staged_records), self.batch_size):
                batch = staged_records[i:i + self.batch_size]
                batch_count += 1
                
                logger.info(f"Processing batch {batch_count} ({len(batch)} records)")
                
                batch_result = await self._process_record_batch(
                    batch, 
                    promotion_threshold or self.default_promotion_threshold,
                    dry_run
                )
                
                result.promoted += batch_result.promoted
                result.discarded += batch_result.discarded
                result.errors += batch_result.errors
                result.promoted_records.extend(batch_result.promoted_records)
                result.discarded_records.extend(batch_result.discarded_records)
                result.error_messages.extend(batch_result.error_messages)
            
            end_time = datetime.utcnow()
            result.processing_time = (end_time - start_time).total_seconds()
            
            logger.info(f"Promotion completed: {result.promoted} promoted, {result.discarded} discarded, {result.errors} errors")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to promote staged records: {e}")
            result.errors += 1
            result.error_messages.append(str(e))
            return result
    
    async def _get_staged_records(self, 
                                tenant_id: str, 
                                domain_id: Optional[str] = None,
                                max_records: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get staged records that need evaluation"""
        
        all_records = await self.db_service.get_records(tenant_id, limit=10000)
        
        staged_records = []
        for record in all_records:
            if record.get('schema_id') != 'staged_rss_item':
                continue
            
            staging_metadata = record.get('data', {}).get('staging_metadata', {})
            if not staging_metadata:
                continue
            
            if domain_id and staging_metadata.get('domain_id') != domain_id:
                continue
            
            if not staging_metadata.get('requires_domain_filtering', False):
                staged_records.append(record)
                continue
            
            ingestion_time = staging_metadata.get('ingestion_timestamp')
            if ingestion_time:
                try:
                    ingestion_dt = datetime.fromisoformat(ingestion_time.replace('Z', '+00:00'))
                    age_days = (datetime.utcnow() - ingestion_dt.replace(tzinfo=None)).days
                    
                    if age_days > self.max_age_days:
                        logger.info(f"Auto-discarding record {record['uuid']} (age: {age_days} days)")
                        continue
                except Exception as e:
                    logger.warning(f"Failed to parse ingestion timestamp for record {record['uuid']}: {e}")
            
            staged_records.append(record)
        
        if max_records:
            staged_records = staged_records[:max_records]
        
        return staged_records
    
    async def _process_record_batch(self, 
                                  records: List[Dict[str, Any]], 
                                  promotion_threshold: float,
                                  dry_run: bool) -> PromotionResult:
        """Process a batch of records for promotion"""
        
        batch_result = PromotionResult()
        
        for record in records:
            try:
                should_promote, relevance_score, reason = await self._evaluate_record_for_promotion(
                    record, promotion_threshold
                )
                
                if should_promote:
                    if not dry_run:
                        promoted_record = await self._promote_record(record)
                        if promoted_record:
                            batch_result.promoted += 1
                            batch_result.promoted_records.append({
                                'uuid': record['uuid'],
                                'title': record.get('data', {}).get('title', 'Unknown'),
                                'relevance_score': relevance_score,
                                'reason': reason
                            })
                        else:
                            batch_result.errors += 1
                            batch_result.error_messages.append(f"Failed to promote record {record['uuid']}")
                    else:
                        batch_result.promoted += 1
                        batch_result.promoted_records.append({
                            'uuid': record['uuid'],
                            'title': record.get('data', {}).get('title', 'Unknown'),
                            'relevance_score': relevance_score,
                            'reason': reason
                        })
                else:
                    if not dry_run:
                        discarded = await self._discard_record(record)
                        if discarded:
                            batch_result.discarded += 1
                            batch_result.discarded_records.append({
                                'uuid': record['uuid'],
                                'title': record.get('data', {}).get('title', 'Unknown'),
                                'relevance_score': relevance_score,
                                'reason': reason
                            })
                        else:
                            batch_result.errors += 1
                            batch_result.error_messages.append(f"Failed to discard record {record['uuid']}")
                    else:
                        batch_result.discarded += 1
                        batch_result.discarded_records.append({
                            'uuid': record['uuid'],
                            'title': record.get('data', {}).get('title', 'Unknown'),
                            'relevance_score': relevance_score,
                            'reason': reason
                        })
                
            except Exception as e:
                logger.error(f"Failed to process record {record.get('uuid', 'unknown')}: {e}")
                batch_result.errors += 1
                batch_result.error_messages.append(f"Record {record.get('uuid', 'unknown')}: {str(e)}")
        
        return batch_result
    
    async def _evaluate_record_for_promotion(self, 
                                           record: Dict[str, Any], 
                                           promotion_threshold: float) -> Tuple[bool, float, str]:
        """
        Evaluate whether a record should be promoted
        
        Returns:
            (should_promote, relevance_score, reason)
        """
        
        try:
            staging_metadata = record.get('data', {}).get('staging_metadata', {})
            
            if not staging_metadata.get('requires_domain_filtering', False):
                return True, 1.0, "Auto-promote: No domain filtering required"
            
            domain_id = staging_metadata.get('domain_id')
            if not domain_id:
                return False, 0.0, "No domain specified for filtering"
            
            domain = self.domain_service.get_domain(domain_id)
            if not domain:
                return False, 0.0, f"Domain {domain_id} not found"
            
            record_data = record.get('data', {})
            text_content = f"{record_data.get('title', '')} {record_data.get('description', '')} {record_data.get('content', '')}"
            
            relevance_score = self.domain_service.calculate_relevance_score(text_content, domain)
            
            should_promote = relevance_score >= promotion_threshold
            
            if should_promote:
                reason = f"Relevance score {relevance_score:.3f} >= threshold {promotion_threshold}"
            else:
                reason = f"Relevance score {relevance_score:.3f} < threshold {promotion_threshold}"
            
            return should_promote, relevance_score, reason
            
        except Exception as e:
            logger.error(f"Failed to evaluate record {record.get('uuid', 'unknown')}: {e}")
            return False, 0.0, f"Evaluation error: {str(e)}"
    
    async def _promote_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Promote a staged record to permanent storage"""
        
        try:
            promoted_data = record['data'].copy()
            
            if 'staging_metadata' in promoted_data:
                staging_metadata = promoted_data.pop('staging_metadata')
                
                promoted_data['promotion_metadata'] = {
                    'promoted_at': datetime.utcnow().isoformat(),
                    'promoted_from': 'staged_rss_item',
                    'original_ingestion_timestamp': staging_metadata.get('ingestion_timestamp'),
                    'domain_id': staging_metadata.get('domain_id'),
                    'promotion_reason': 'Passed relevance threshold'
                }
            
            promoted_wrapper = UniversalWrapper(
                uuid=record['uuid'],
                created_at=datetime.fromisoformat(record['created_at']),
                updated_at=datetime.utcnow(),
                schema_id="permanent_rss_item",
                tenant_id=record['tenant_id'],
                source=Source(**record['source']),
                data=promoted_data
            )
            
            content_hash = record.get('content_hash', '')
            saved = await self.db_service.save_record(promoted_wrapper, content_hash)
            
            if saved:
                logger.info(f"Successfully promoted record {record['uuid']}")
                return promoted_wrapper.model_dump()
            else:
                logger.error(f"Failed to save promoted record {record['uuid']}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to promote record {record.get('uuid', 'unknown')}: {e}")
            return None
    
    async def _discard_record(self, record: Dict[str, Any]) -> bool:
        """Discard a staged record (remove from storage)"""
        
        try:
            discarded_data = record['data'].copy()
            
            if 'staging_metadata' in discarded_data:
                staging_metadata = discarded_data.pop('staging_metadata')
                
                discarded_data['discard_metadata'] = {
                    'discarded_at': datetime.utcnow().isoformat(),
                    'discarded_from': 'staged_rss_item',
                    'original_ingestion_timestamp': staging_metadata.get('ingestion_timestamp'),
                    'domain_id': staging_metadata.get('domain_id'),
                    'discard_reason': 'Failed relevance threshold'
                }
            
            discarded_wrapper = UniversalWrapper(
                uuid=record['uuid'],
                created_at=datetime.fromisoformat(record['created_at']),
                updated_at=datetime.utcnow(),
                schema_id="discarded_rss_item",
                tenant_id=record['tenant_id'],
                source=Source(**record['source']),
                data=discarded_data
            )
            
            content_hash = record.get('content_hash', '')
            saved = await self.db_service.save_record(discarded_wrapper, content_hash)
            
            if saved:
                logger.info(f"Successfully discarded record {record['uuid']}")
                return True
            else:
                logger.error(f"Failed to save discarded record {record['uuid']}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to discard record {record.get('uuid', 'unknown')}: {e}")
            return False
    
    async def get_promotion_statistics(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Get statistics about record promotion for a tenant"""
        
        try:
            all_records = await self.db_service.get_records(tenant_id, limit=10000)
            
            stats = {
                'total_records': len(all_records),
                'staged_records': 0,
                'permanent_records': 0,
                'discarded_records': 0,
                'by_domain': {},
                'by_age': {
                    'last_24h': 0,
                    'last_7d': 0,
                    'last_30d': 0,
                    'older': 0
                }
            }
            
            now = datetime.utcnow()
            
            for record in all_records:
                schema_id = record.get('schema_id', '')
                
                if schema_id == 'staged_rss_item':
                    stats['staged_records'] += 1
                elif schema_id == 'permanent_rss_item':
                    stats['permanent_records'] += 1
                elif schema_id == 'discarded_rss_item':
                    stats['discarded_records'] += 1
                
                data = record.get('data', {})
                domain_id = None
                
                if 'staging_metadata' in data:
                    domain_id = data['staging_metadata'].get('domain_id')
                elif 'promotion_metadata' in data:
                    domain_id = data['promotion_metadata'].get('domain_id')
                elif 'discard_metadata' in data:
                    domain_id = data['discard_metadata'].get('domain_id')
                
                if domain_id:
                    if domain_id not in stats['by_domain']:
                        stats['by_domain'][domain_id] = {
                            'staged': 0,
                            'permanent': 0,
                            'discarded': 0
                        }
                    
                    if schema_id == 'staged_rss_item':
                        stats['by_domain'][domain_id]['staged'] += 1
                    elif schema_id == 'permanent_rss_item':
                        stats['by_domain'][domain_id]['permanent'] += 1
                    elif schema_id == 'discarded_rss_item':
                        stats['by_domain'][domain_id]['discarded'] += 1
                
                try:
                    created_at = datetime.fromisoformat(record['created_at'])
                    age = (now - created_at).total_seconds()
                    
                    if age < 86400:
                        stats['by_age']['last_24h'] += 1
                    elif age < 604800:
                        stats['by_age']['last_7d'] += 1
                    elif age < 2592000:
                        stats['by_age']['last_30d'] += 1
                    else:
                        stats['by_age']['older'] += 1
                except:
                    stats['by_age']['older'] += 1
            
            if stats['total_records'] > 0:
                stats['promotion_rate'] = stats['permanent_records'] / stats['total_records']
                stats['discard_rate'] = stats['discarded_records'] / stats['total_records']
                stats['staging_rate'] = stats['staged_records'] / stats['total_records']
            else:
                stats['promotion_rate'] = 0
                stats['discard_rate'] = 0
                stats['staging_rate'] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get promotion statistics: {e}")
            return {'error': str(e)}
    
    async def cleanup_old_records(self, 
                                tenant_id: str = "default",
                                max_age_days: int = 90,
                                dry_run: bool = False) -> Dict[str, Any]:
        """Clean up old discarded records to free storage space"""
        
        try:
            all_records = await self.db_service.get_records(tenant_id, limit=10000)
            
            cleanup_stats = {
                'total_evaluated': 0,
                'cleaned_up': 0,
                'errors': 0,
                'error_messages': []
            }
            
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            
            for record in all_records:
                if record.get('schema_id') != 'discarded_rss_item':
                    continue
                
                cleanup_stats['total_evaluated'] += 1
                
                try:
                    discard_metadata = record.get('data', {}).get('discard_metadata', {})
                    discarded_at = discard_metadata.get('discarded_at')
                    
                    if discarded_at:
                        discarded_dt = datetime.fromisoformat(discarded_at)
                        if discarded_dt < cutoff_date:
                            if not dry_run:
                                logger.info(f"Would delete old discarded record {record['uuid']}")
                            
                            cleanup_stats['cleaned_up'] += 1
                
                except Exception as e:
                    cleanup_stats['errors'] += 1
                    cleanup_stats['error_messages'].append(f"Record {record.get('uuid', 'unknown')}: {str(e)}")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")
            return {'error': str(e)}
