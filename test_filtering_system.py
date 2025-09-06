#!/usr/bin/env python3
"""
Test Filtering System for Universal Database

Tests the record filtering logic with synthetic data to validate
temporary-to-permanent promotion accuracy.
"""

import json
import asyncio
import sys
import os
from typing import List, Dict, Any, Tuple
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/universal-db/rss_ingestion')
os.chdir('/home/ubuntu/universal-db/rss_ingestion')

from app.models import DomainTemplate, ManualFilterRequest
from app.services import DomainService, DatabaseService, VectorService, RSSService
from app.promotion_service import RecordPromotionService

class FilteringSystemTester:
    """Test the filtering system with synthetic data"""
    
    def __init__(self):
        self.db_service = DatabaseService()
        self.vector_service = VectorService()
        self.domain_service = DomainService()
        self.rss_service = RSSService(self.db_service, self.vector_service, self.domain_service)
        self.promotion_service = RecordPromotionService(self.db_service, self.domain_service, self.vector_service)
        
        self.test_results = {
            'domain_filtering': {},
            'manual_filtering': {},
            'promotion_logic': {},
            'overall_metrics': {}
        }
    
    async def setup(self):
        """Initialize services"""
        await self.db_service.init_db()
        await self.vector_service.init_collection()
        print("Test environment initialized")
    
    def load_test_dataset(self, filename: str = "test_dataset.json") -> Dict[str, Any]:
        """Load test dataset from JSON file"""
        try:
            with open(filename, 'r') as f:
                dataset = json.load(f)
            print(f"Loaded test dataset with {dataset['metadata']['total_articles']} articles")
            return dataset
        except FileNotFoundError:
            print(f"Test dataset {filename} not found. Run test_data_generator.py first.")
            return None
    
    async def test_domain_filtering_accuracy(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Test domain filtering accuracy with known signal/noise ratios"""
        
        print("\n🧪 Testing Domain Filtering Accuracy...")
        
        results = {}
        
        fort_worth_articles = dataset['articles']['fort_worth_political']
        fort_worth_results = await self._test_domain_category(
            'fort_worth_political', 
            fort_worth_articles,
            expected_signal_ratio=0.85
        )
        results['fort_worth_political'] = fort_worth_results
        
        tech_domain = await self._create_tech_startup_domain()
        tech_articles = dataset['articles']['tech_startups']
        tech_results = await self._test_domain_category(
            'tech_startups',
            tech_articles,
            expected_signal_ratio=0.60,
            domain=tech_domain
        )
        results['tech_startups'] = tech_results
        
        mixed_domain = await self._create_mixed_content_domain()
        mixed_articles = dataset['articles']['mixed_content']
        mixed_results = await self._test_domain_category(
            'mixed_content',
            mixed_articles,
            expected_signal_ratio=0.25,
            domain=mixed_domain
        )
        results['mixed_content'] = mixed_results
        
        self.test_results['domain_filtering'] = results
        return results
    
    async def _test_domain_category(self, category: str, articles: List[Dict], expected_signal_ratio: float, domain: DomainTemplate = None) -> Dict[str, Any]:
        """Test filtering accuracy for a specific domain category"""
        
        if domain is None:
            domain = await self.domain_service.get_domain('fort_worth_political')
        
        print(f"  Testing {category} domain ({len(articles)} articles)...")
        
        true_positives = 0  # Correctly identified signal
        false_positives = 0  # Incorrectly identified signal (noise marked as signal)
        true_negatives = 0  # Correctly identified noise
        false_negatives = 0  # Incorrectly identified noise (signal marked as noise)
        
        relevance_scores = []
        
        for article in articles:
            text = f"{article['title']} {article['description']} {article['content']}"
            relevance_score = self.domain_service.calculate_relevance_score(text, domain)
            relevance_scores.append(relevance_score)
            
            predicted_keep = relevance_score >= domain.min_relevance_score
            actual_keep = article['expected_outcome'] == 'KEEP'
            
            if predicted_keep and actual_keep:
                true_positives += 1
            elif predicted_keep and not actual_keep:
                false_positives += 1
            elif not predicted_keep and not actual_keep:
                true_negatives += 1
            elif not predicted_keep and actual_keep:
                false_negatives += 1
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (true_positives + true_negatives) / len(articles)
        
        avg_relevance_score = sum(relevance_scores) / len(relevance_scores)
        
        results = {
            'category': category,
            'total_articles': len(articles),
            'expected_signal_ratio': expected_signal_ratio,
            'confusion_matrix': {
                'true_positives': true_positives,
                'false_positives': false_positives,
                'true_negatives': true_negatives,
                'false_negatives': false_negatives
            },
            'metrics': {
                'precision': precision,
                'recall': recall,
                'f1_score': f1_score,
                'accuracy': accuracy,
                'avg_relevance_score': avg_relevance_score
            },
            'threshold': domain.min_relevance_score,
            'domain_config': {
                'keywords_count': len(domain.keywords),
                'entities_count': len(domain.entities),
                'locations_count': len(domain.locations),
                'exclude_keywords_count': len(domain.exclude_keywords)
            }
        }
        
        print(f"    Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1_score:.3f}, Accuracy: {accuracy:.3f}")
        
        return results
    
    async def _create_tech_startup_domain(self) -> DomainTemplate:
        """Create tech startup domain for testing"""
        
        domain = DomainTemplate(
            domain_id="tech_startups_test",
            name="Tech Startups Test",
            description="Technology startups, venture capital, and entrepreneurship news",
            ai_prompt="Filter articles about technology startups, venture capital funding, entrepreneurship, and innovation. Keep articles about startup funding rounds, new company launches, accelerator programs, and entrepreneur profiles. Exclude general technology news, consumer products, and established company news.",
            keywords=[
                "startup", "venture capital", "funding", "entrepreneur", "accelerator",
                "incubator", "seed round", "series a", "series b", "ipo", "unicorn",
                "angel investor", "pitch", "innovation", "disrupt", "scale"
            ],
            entities=[
                "Y Combinator", "Techstars", "Andreessen Horowitz", "Sequoia Capital",
                "Kleiner Perkins", "Accel Partners", "Greylock Partners"
            ],
            locations=[
                "Silicon Valley", "Austin", "Dallas", "Houston", "San Antonio",
                "Texas", "California", "New York", "Boston"
            ],
            exclude_keywords=[
                "consumer", "retail", "gaming", "entertainment", "sports",
                "weather", "celebrity", "fashion", "travel", "food"
            ],
            min_relevance_score=0.4
        )
        
        self.domain_service.domains[domain.domain_id] = domain
        return domain
    
    async def _create_mixed_content_domain(self) -> DomainTemplate:
        """Create mixed content domain for testing"""
        
        domain = DomainTemplate(
            domain_id="business_innovation_test",
            name="Business Innovation Test",
            description="Local business innovation and entrepreneurship",
            ai_prompt="Filter articles about local business innovation, entrepreneurship, and economic development. Keep articles about new business launches, innovation programs, economic growth initiatives, and entrepreneur spotlights. Exclude entertainment, sports, and lifestyle content.",
            keywords=[
                "business", "innovation", "entrepreneur", "economic", "development",
                "local", "small business", "startup", "growth", "initiative"
            ],
            entities=[
                "Chamber of Commerce", "Economic Development", "Small Business Administration",
                "Innovation Hub", "Business Incubator"
            ],
            locations=[
                "Texas", "Austin", "Dallas", "Houston", "San Antonio",
                "Fort Worth", "North Texas", "Central Texas"
            ],
            exclude_keywords=[
                "entertainment", "celebrity", "sports", "fashion", "travel",
                "food", "recipe", "movie", "music", "gaming"
            ],
            min_relevance_score=0.3
        )
        
        self.domain_service.domains[domain.domain_id] = domain
        return domain
    
    async def test_manual_filtering_accuracy(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Test manual filtering with various prompts"""
        
        print("\n🧪 Testing Manual Filtering Accuracy...")
        
        results = {}
        
        test_prompts = [
            {
                'name': 'fort_worth_government',
                'prompt': "Keep articles about Fort Worth city government, politics, and municipal affairs. Include city council meetings, mayoral announcements, budget discussions, and local government initiatives.",
                'include_keywords': ['fort worth', 'city council', 'mayor', 'government', 'municipal'],
                'exclude_keywords': ['sports', 'entertainment', 'weather', 'restaurant'],
                'min_score': 0.3,
                'test_articles': dataset['articles']['fort_worth_political']
            },
            {
                'name': 'tech_startup_funding',
                'prompt': "Keep articles about technology startup funding, venture capital, and entrepreneurship. Include funding rounds, new company launches, and innovation programs.",
                'include_keywords': ['startup', 'venture capital', 'funding', 'entrepreneur', 'innovation'],
                'exclude_keywords': ['consumer', 'retail', 'gaming', 'entertainment'],
                'min_score': 0.4,
                'test_articles': dataset['articles']['tech_startups']
            },
            {
                'name': 'business_innovation',
                'prompt': "Keep articles about local business innovation and economic development. Include new business launches and entrepreneur spotlights.",
                'include_keywords': ['business', 'innovation', 'entrepreneur', 'economic', 'development'],
                'exclude_keywords': ['entertainment', 'celebrity', 'sports', 'fashion', 'travel'],
                'min_score': 0.25,
                'test_articles': dataset['articles']['mixed_content']
            }
        ]
        
        for prompt_config in test_prompts:
            prompt_results = await self._test_manual_filter_prompt(prompt_config)
            results[prompt_config['name']] = prompt_results
        
        self.test_results['manual_filtering'] = results
        return results
    
    async def _test_manual_filter_prompt(self, prompt_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test a specific manual filter prompt"""
        
        print(f"  Testing prompt: {prompt_config['name']}...")
        
        articles = prompt_config['test_articles']
        include_keywords = prompt_config['include_keywords']
        exclude_keywords = prompt_config['exclude_keywords']
        min_score = prompt_config['min_score']
        
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0
        
        for article in articles:
            text = f"{article['title']} {article['description']} {article['content']}".lower()
            
            include_matches = sum(1 for keyword in include_keywords if keyword.lower() in text)
            include_score = include_matches / len(include_keywords) if include_keywords else 1.0
            
            has_exclude = any(keyword.lower() in text for keyword in exclude_keywords)
            
            predicted_keep = include_score >= min_score and not has_exclude
            actual_keep = article['expected_outcome'] == 'KEEP'
            
            if predicted_keep and actual_keep:
                true_positives += 1
            elif predicted_keep and not actual_keep:
                false_positives += 1
            elif not predicted_keep and not actual_keep:
                true_negatives += 1
            elif not predicted_keep and actual_keep:
                false_negatives += 1
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (true_positives + true_negatives) / len(articles)
        
        results = {
            'prompt_name': prompt_config['name'],
            'total_articles': len(articles),
            'confusion_matrix': {
                'true_positives': true_positives,
                'false_positives': false_positives,
                'true_negatives': true_negatives,
                'false_negatives': false_negatives
            },
            'metrics': {
                'precision': precision,
                'recall': recall,
                'f1_score': f1_score,
                'accuracy': accuracy
            },
            'config': {
                'include_keywords': include_keywords,
                'exclude_keywords': exclude_keywords,
                'min_score': min_score
            }
        }
        
        print(f"    Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1_score:.3f}, Accuracy: {accuracy:.3f}")
        
        return results
    
    async def test_promotion_logic(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Test staging to permanent promotion logic"""
        
        print("\n🧪 Testing Promotion Logic...")
        
        all_articles = []
        for category_articles in dataset['articles'].values():
            all_articles.extend(category_articles)
        
        thresholds = [0.2, 0.3, 0.4, 0.5]
        results = {}
        
        for threshold in thresholds:
            threshold_results = await self._test_promotion_threshold(all_articles, threshold)
            results[f'threshold_{threshold}'] = threshold_results
        
        self.test_results['promotion_logic'] = results
        return results
    
    async def _test_promotion_threshold(self, articles: List[Dict], threshold: float) -> Dict[str, Any]:
        """Test promotion logic with specific threshold"""
        
        print(f"  Testing promotion threshold: {threshold}...")
        
        promoted = 0
        discarded = 0
        correct_promotions = 0
        correct_discards = 0
        
        for article in articles:
            relevance_score = article['relevance_score_expected']
            
            should_promote = relevance_score >= threshold
            should_keep = article['expected_outcome'] == 'KEEP'
            
            if should_promote:
                promoted += 1
                if should_keep:
                    correct_promotions += 1
            else:
                discarded += 1
                if not should_keep:
                    correct_discards += 1
        
        promotion_accuracy = correct_promotions / promoted if promoted > 0 else 0
        discard_accuracy = correct_discards / discarded if discarded > 0 else 0
        overall_accuracy = (correct_promotions + correct_discards) / len(articles)
        
        results = {
            'threshold': threshold,
            'total_articles': len(articles),
            'promoted': promoted,
            'discarded': discarded,
            'correct_promotions': correct_promotions,
            'correct_discards': correct_discards,
            'metrics': {
                'promotion_accuracy': promotion_accuracy,
                'discard_accuracy': discard_accuracy,
                'overall_accuracy': overall_accuracy,
                'promotion_rate': promoted / len(articles),
                'discard_rate': discarded / len(articles)
            }
        }
        
        print(f"    Promoted: {promoted}, Discarded: {discarded}, Accuracy: {overall_accuracy:.3f}")
        
        return results
    
    def calculate_overall_metrics(self) -> Dict[str, Any]:
        """Calculate overall system performance metrics"""
        
        print("\n📊 Calculating Overall Metrics...")
        
        domain_metrics = []
        manual_metrics = []
        
        for category, results in self.test_results['domain_filtering'].items():
            domain_metrics.append(results['metrics'])
        
        for prompt, results in self.test_results['manual_filtering'].items():
            manual_metrics.append(results['metrics'])
        
        avg_domain_precision = sum(m['precision'] for m in domain_metrics) / len(domain_metrics)
        avg_domain_recall = sum(m['recall'] for m in domain_metrics) / len(domain_metrics)
        avg_domain_f1 = sum(m['f1_score'] for m in domain_metrics) / len(domain_metrics)
        
        avg_manual_precision = sum(m['precision'] for m in manual_metrics) / len(manual_metrics)
        avg_manual_recall = sum(m['recall'] for m in manual_metrics) / len(manual_metrics)
        avg_manual_f1 = sum(m['f1_score'] for m in manual_metrics) / len(manual_metrics)
        
        best_threshold = None
        best_accuracy = 0
        for threshold_key, results in self.test_results['promotion_logic'].items():
            accuracy = results['metrics']['overall_accuracy']
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_threshold = results['threshold']
        
        overall_metrics = {
            'domain_filtering': {
                'avg_precision': avg_domain_precision,
                'avg_recall': avg_domain_recall,
                'avg_f1_score': avg_domain_f1
            },
            'manual_filtering': {
                'avg_precision': avg_manual_precision,
                'avg_recall': avg_manual_recall,
                'avg_f1_score': avg_manual_f1
            },
            'promotion_logic': {
                'best_threshold': best_threshold,
                'best_accuracy': best_accuracy
            },
            'recommendations': self._generate_recommendations()
        }
        
        self.test_results['overall_metrics'] = overall_metrics
        
        print(f"  Domain Filtering - Precision: {avg_domain_precision:.3f}, Recall: {avg_domain_recall:.3f}, F1: {avg_domain_f1:.3f}")
        print(f"  Manual Filtering - Precision: {avg_manual_precision:.3f}, Recall: {avg_manual_recall:.3f}, F1: {avg_manual_f1:.3f}")
        print(f"  Best Promotion Threshold: {best_threshold} (Accuracy: {best_accuracy:.3f})")
        
        return overall_metrics
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        
        recommendations = []
        
        domain_results = self.test_results['domain_filtering']
        for category, results in domain_results.items():
            precision = results['metrics']['precision']
            recall = results['metrics']['recall']
            
            if precision < 0.7:
                recommendations.append(f"Improve {category} domain precision by refining keywords and exclude terms")
            if recall < 0.6:
                recommendations.append(f"Improve {category} domain recall by adding more relevant keywords")
        
        manual_results = self.test_results['manual_filtering']
        for prompt, results in manual_results.items():
            precision = results['metrics']['precision']
            if precision < 0.75:
                recommendations.append(f"Refine manual filter '{prompt}' to reduce false positives")
        
        promotion_results = self.test_results['promotion_logic']
        best_threshold = None
        best_accuracy = 0
        for threshold_key, results in promotion_results.items():
            accuracy = results['metrics']['overall_accuracy']
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_threshold = results['threshold']
        
        if best_accuracy < 0.8:
            recommendations.append("Consider implementing more sophisticated promotion logic beyond simple threshold")
        
        if not recommendations:
            recommendations.append("System performance meets target thresholds - ready for production")
        
        return recommendations
    
    def save_results(self, filename: str = "filtering_test_results.json"):
        """Save test results to JSON file"""
        
        self.test_results['test_metadata'] = {
            'timestamp': datetime.utcnow().isoformat(),
            'test_version': '1.0',
            'total_articles_tested': sum(
                results['total_articles'] 
                for results in self.test_results['domain_filtering'].values()
            )
        }
        
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\nTest results saved to {filename}")
    
    def print_summary(self):
        """Print test summary"""
        
        print("\n" + "="*60)
        print("🎯 FILTERING SYSTEM TEST SUMMARY")
        print("="*60)
        
        overall = self.test_results['overall_metrics']
        
        print(f"\n📈 DOMAIN FILTERING PERFORMANCE:")
        print(f"  Average Precision: {overall['domain_filtering']['avg_precision']:.3f}")
        print(f"  Average Recall:    {overall['domain_filtering']['avg_recall']:.3f}")
        print(f"  Average F1 Score:  {overall['domain_filtering']['avg_f1_score']:.3f}")
        
        print(f"\n🎛️  MANUAL FILTERING PERFORMANCE:")
        print(f"  Average Precision: {overall['manual_filtering']['avg_precision']:.3f}")
        print(f"  Average Recall:    {overall['manual_filtering']['avg_recall']:.3f}")
        print(f"  Average F1 Score:  {overall['manual_filtering']['avg_f1_score']:.3f}")
        
        print(f"\n⚡ PROMOTION LOGIC:")
        print(f"  Best Threshold:    {overall['promotion_logic']['best_threshold']}")
        print(f"  Best Accuracy:     {overall['promotion_logic']['best_accuracy']:.3f}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(overall['recommendations'], 1):
            print(f"  {i}. {rec}")
        
    
    async def test_promotion_service_integration(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Test the complete promotion workflow with synthetic data"""
        
        print("Testing promotion service integration...")
        
        try:
            promotion_results = {}
            
            thresholds = [0.2, 0.3, 0.4, 0.5]
            
            for threshold in thresholds:
                print(f"Testing promotion with threshold {threshold}")
                
                result = await self.promotion_service.promote_staged_records(
                    promotion_threshold=threshold,
                    max_records=50,
                    dry_run=True
                )
                
                promotion_results[f'threshold_{threshold}'] = {
                    'total_evaluated': result.total_evaluated,
                    'promoted': result.promoted,
                    'discarded': result.discarded,
                    'promotion_rate': result.promoted / result.total_evaluated if result.total_evaluated > 0 else 0,
                    'processing_time': result.processing_time,
                    'avg_time_per_record': result.processing_time / result.total_evaluated if result.total_evaluated > 0 else 0
                }
            
            stats = await self.promotion_service.get_promotion_statistics()
            
            promotion_results['statistics'] = {
                'total_records': stats.get('total_records', 0),
                'staged_records': stats.get('staged_records', 0),
                'permanent_records': stats.get('permanent_records', 0),
                'discarded_records': stats.get('discarded_records', 0),
                'promotion_rate': stats.get('promotion_rate', 0),
                'by_domain': stats.get('by_domain', {})
            }
            
            performance_target_met = all(
                result['avg_time_per_record'] < 0.1 
                for result in promotion_results.values() 
                if isinstance(result, dict) and 'avg_time_per_record' in result
            )
            
            promotion_results['performance_analysis'] = {
                'meets_100ms_target': performance_target_met,
                'fastest_threshold': min(
                    [k for k in promotion_results.keys() if k.startswith('threshold_')],
                    key=lambda k: promotion_results[k].get('avg_time_per_record', float('inf'))
                    if isinstance(promotion_results[k], dict) and 'avg_time_per_record' in promotion_results[k]
                    else float('inf'),
                    default='none'
                )
            }
            
            return promotion_results
            
        except Exception as e:
            print(f"Error testing promotion service: {e}")
            return {'error': str(e)}

        print("\n" + "="*60)


async def main():
    """Run the complete filtering system test suite"""
    
    print("🚀 Starting Universal Database Filtering System Tests")
    print("="*60)
    
    tester = FilteringSystemTester()
    await tester.setup()
    
    dataset = tester.load_test_dataset("/home/ubuntu/universal-db/test_dataset.json")
    if not dataset:
        print("❌ Cannot proceed without test dataset")
        return
    
    try:
        await tester.test_domain_filtering_accuracy(dataset)
        await tester.test_manual_filtering_accuracy(dataset)
        await tester.test_promotion_logic(dataset)
        
        tester.calculate_overall_metrics()
        
        tester.save_results()
        tester.print_summary()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
