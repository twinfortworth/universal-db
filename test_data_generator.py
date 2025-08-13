#!/usr/bin/env python3
"""
Test Data Generator for Universal Database Record Filtering System

Creates synthetic RSS feeds with known signal/noise patterns to test
the temporary-to-permanent record promotion logic.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

class TestRSSGenerator:
    """Generate test RSS feeds with controlled signal/noise ratios"""
    
    def __init__(self):
        self.base_date = datetime.utcnow() - timedelta(days=30)
        
    def generate_fort_worth_political_articles(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate Fort Worth political articles with 85% signal, 15% noise"""
        
        signal_templates = [
            "Fort Worth City Council approves ${amount} budget for {year}",
            "Mayor Parker announces new {project} initiative in {district}",
            "Tarrant County commissioners vote on {topic} proposal",
            "Fort Worth ISD board meeting discusses {issue}",
            "Trinity Metro expands {service} in {area} district",
            "City of Fort Worth launches {program} for residents",
            "Fort Worth municipal {department} receives funding increase",
            "Local government addresses {concern} in community meeting",
            "Fort Worth zoning committee reviews {development} project",
            "Tarrant County budget allocates funds for {infrastructure}"
        ]
        
        noise_templates = [
            "Dallas Cowboys {action} at AT&T Stadium in Arlington",
            "Fort Worth restaurant review: Best {cuisine} in Texas",
            "Weather forecast: {condition} expected in DFW area",
            "Concert review: {artist} performs at Fort Worth Stockyards",
            "Fort Worth Zoo welcomes new {animal} exhibit",
            "TCU Horned Frogs {sport} team {result} in conference play",
            "Shopping guide: {store} opens new location in Fort Worth",
            "Entertainment: {event} festival coming to downtown",
            "Travel: Top {number} attractions to visit in Fort Worth",
            "Food truck {name} serves {dish} at local events"
        ]
        
        articles = []
        signal_count = int(count * 0.85)  # 85% signal
        noise_count = count - signal_count  # 15% noise
        
        for i in range(signal_count):
            template = random.choice(signal_templates)
            article = self._fill_template(template, {
                'amount': random.choice(['$2.1B', '$500M', '$1.8B', '$750M']),
                'year': random.choice(['2024', '2025']),
                'project': random.choice(['downtown development', 'infrastructure', 'housing', 'transportation']),
                'district': random.choice(['Alliance', 'Cultural District', 'Downtown', 'Southside']),
                'topic': random.choice(['transportation bond', 'tax increment', 'zoning change', 'budget amendment']),
                'issue': random.choice(['teacher pay raises', 'school funding', 'facility improvements', 'technology upgrades']),
                'service': random.choice(['bus routes', 'rail service', 'bike sharing', 'transit hubs']),
                'area': random.choice(['Alliance', 'Near Southside', 'West 7th', 'Medical District']),
                'program': random.choice(['affordable housing', 'small business support', 'infrastructure repair', 'community development']),
                'department': random.choice(['Police Department', 'Fire Department', 'Parks & Recreation', 'Public Works']),
                'concern': random.choice(['traffic safety', 'neighborhood development', 'public safety', 'environmental issues']),
                'development': random.choice(['mixed-use', 'residential', 'commercial', 'industrial']),
                'infrastructure': random.choice(['road improvements', 'water systems', 'broadband expansion', 'public transit'])
            })
            
            articles.append({
                'title': article,
                'description': f"Local government news about {article.lower()}",
                'link': f"https://example.com/fort-worth-political/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This contains relevant political and governmental information for Fort Worth residents.",
                'author': random.choice(['City Reporter', 'Government Affairs', 'Municipal News', 'Local Politics']),
                'tags': ['fort-worth', 'politics', 'government', 'municipal'],
                'expected_outcome': 'KEEP',
                'category': 'signal',
                'relevance_score_expected': random.uniform(0.7, 0.95)
            })
        
        for i in range(noise_count):
            template = random.choice(noise_templates)
            article = self._fill_template(template, {
                'action': random.choice(['win playoff game', 'sign new player', 'announce schedule', 'hold practice']),
                'cuisine': random.choice(['BBQ', 'Tex-Mex', 'Italian', 'Asian']),
                'condition': random.choice(['Rain', 'Snow', 'Thunderstorms', 'Clear skies']),
                'artist': random.choice(['Country Star', 'Rock Band', 'Jazz Ensemble', 'Pop Artist']),
                'animal': random.choice(['elephant', 'giraffe', 'penguin', 'tiger']),
                'sport': random.choice(['football', 'basketball', 'baseball', 'soccer']),
                'result': random.choice(['wins championship', 'loses close game', 'advances to playoffs', 'sets new record']),
                'store': random.choice(['Target', 'Walmart', 'Best Buy', 'Home Depot']),
                'event': random.choice(['Music', 'Food', 'Art', 'Cultural']),
                'number': random.choice(['5', '10', '15', '20']),
                'name': random.choice(['Taco Truck', 'BBQ Express', 'Burger Mobile', 'Pizza Wagon']),
                'dish': random.choice(['tacos', 'barbecue', 'burgers', 'pizza'])
            })
            
            articles.append({
                'title': article,
                'description': f"Entertainment and lifestyle news about {article.lower()}",
                'link': f"https://example.com/fort-worth-entertainment/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This is entertainment, sports, or lifestyle content not related to government.",
                'author': random.choice(['Entertainment Reporter', 'Sports Writer', 'Lifestyle Editor', 'Food Critic']),
                'tags': ['fort-worth', 'entertainment', 'lifestyle', 'sports'],
                'expected_outcome': 'DISCARD',
                'category': 'noise',
                'relevance_score_expected': random.uniform(0.05, 0.25)
            })
        
        return articles
    
    def generate_tech_startup_articles(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate tech startup articles with 60% signal, 40% noise"""
        
        signal_templates = [
            "{company} startup raises ${amount} Series {round} for {technology} platform",
            "New accelerator program launches in {city} tech district",
            "Venture capital funding reaches record high in {state}",
            "{type} company IPO filing shows strong growth metrics",
            "{city} entrepreneur builds {solution} for {industry} market",
            "Tech incubator announces {number} new startups in portfolio",
            "Angel investors fund {technology} startup with ${amount}",
            "Y Combinator graduate {company} expands to {market}",
            "Startup ecosystem grows in {region} with new funding",
            "Unicorn company {name} valued at ${valuation} in latest round"
        ]
        
        noise_templates = [
            "Apple releases new {product} model with updated features",
            "Microsoft stock price hits all-time high after earnings",
            "Tech conference announces keynote speakers for {event}",
            "Consumer electronics sales surge during {season}",
            "Gaming industry reports {metric} growth in {year}",
            "Social media platform updates {feature} for users",
            "Smartphone {brand} launches {model} in {market}",
            "Tech giant acquires {company} for ${amount}",
            "Cloud computing {service} experiences outage",
            "Cybersecurity breach affects {number} users"
        ]
        
        articles = []
        signal_count = int(count * 0.60)  # 60% signal
        noise_count = count - signal_count  # 40% noise
        
        for i in range(signal_count):
            template = random.choice(signal_templates)
            article = self._fill_template(template, {
                'company': random.choice(['TechFlow', 'DataSync', 'CloudBridge', 'AICore', 'DevTools']),
                'amount': random.choice(['$2M', '$5M', '$10M', '$25M', '$50M']),
                'round': random.choice(['A', 'B', 'C', 'Seed']),
                'technology': random.choice(['AI', 'blockchain', 'fintech', 'healthtech', 'edtech']),
                'city': random.choice(['Austin', 'Dallas', 'Houston', 'San Antonio']),
                'state': random.choice(['Texas', 'California', 'New York', 'Florida']),
                'type': random.choice(['SaaS', 'Fintech', 'Healthtech', 'Edtech']),
                'solution': random.choice(['AI platform', 'mobile app', 'web service', 'API platform']),
                'industry': random.choice(['healthcare', 'finance', 'education', 'retail']),
                'number': random.choice(['10', '15', '20', '25']),
                'market': random.choice(['enterprise', 'consumer', 'B2B', 'B2C']),
                'region': random.choice(['Southwest', 'West Coast', 'East Coast', 'Midwest']),
                'name': random.choice(['InnovateCorp', 'TechSolutions', 'DataDriven', 'CloudFirst']),
                'valuation': random.choice(['$1B', '$2B', '$5B', '$10B'])
            })
            
            articles.append({
                'title': article,
                'description': f"Startup and venture capital news about {article.lower()}",
                'link': f"https://example.com/tech-startups/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This covers startup funding, entrepreneurship, and venture capital activity.",
                'author': random.choice(['Tech Reporter', 'Startup News', 'VC Insider', 'Entrepreneur Weekly']),
                'tags': ['startup', 'venture-capital', 'technology', 'entrepreneurship'],
                'expected_outcome': 'KEEP',
                'category': 'signal',
                'relevance_score_expected': random.uniform(0.6, 0.9)
            })
        
        for i in range(noise_count):
            template = random.choice(noise_templates)
            article = self._fill_template(template, {
                'product': random.choice(['iPhone', 'iPad', 'MacBook', 'Apple Watch']),
                'event': random.choice(['CES 2024', 'SXSW', 'TechCrunch Disrupt', 'Web Summit']),
                'season': random.choice(['holidays', 'back-to-school', 'summer', 'spring']),
                'metric': random.choice(['revenue', 'user', 'engagement', 'download']),
                'year': random.choice(['2023', '2024', '2025']),
                'feature': random.choice(['privacy settings', 'user interface', 'messaging', 'video calls']),
                'brand': random.choice(['Samsung', 'Google', 'OnePlus', 'Xiaomi']),
                'model': random.choice(['Galaxy S24', 'Pixel 8', 'OnePlus 12', 'Mi 14']),
                'market': random.choice(['US', 'Europe', 'Asia', 'global']),
                'company': random.choice(['Instagram', 'WhatsApp', 'TikTok', 'Snapchat']),
                'service': random.choice(['AWS', 'Azure', 'Google Cloud', 'Cloudflare']),
                'number': random.choice(['1 million', '5 million', '10 million', '50 million'])
            })
            
            articles.append({
                'title': article,
                'description': f"General technology news about {article.lower()}",
                'link': f"https://example.com/tech-general/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This covers general technology news, not specifically about startups or venture capital.",
                'author': random.choice(['Tech News', 'Industry Analyst', 'Product Review', 'Market Watch']),
                'tags': ['technology', 'consumer', 'enterprise', 'industry'],
                'expected_outcome': 'DISCARD',
                'category': 'noise',
                'relevance_score_expected': random.uniform(0.1, 0.4)
            })
        
        return articles
    
    def generate_mixed_content_articles(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate mixed content with 25% signal, 75% noise"""
        
        signal_templates = [
            "Local business innovation drives economic growth in {city}",
            "Entrepreneur spotlight: Building sustainable solutions for {industry}",
            "Small business {program} launches to support {community}",
            "Innovation hub opens in {district} to foster {type} development",
            "Local {sector} companies collaborate on {project} initiative"
        ]
        
        noise_templates = [
            "Celebrity {name} spotted at {location} restaurant",
            "Movie review: {film} disappoints critics with {rating}",
            "Fashion trends for {season} season include {style}",
            "Travel destinations: Top {number} places to visit in {region}",
            "Recipe: How to make perfect {dish} at home",
            "Sports: {team} {result} in {sport} championship",
            "Weather update: {condition} expected this {timeframe}",
            "Entertainment: {show} premieres on {network} tonight",
            "Health tips: {advice} for better {aspect}",
            "Home improvement: DIY {project} for {room}"
        ]
        
        articles = []
        signal_count = int(count * 0.25)  # 25% signal
        noise_count = count - signal_count  # 75% noise
        
        for i in range(signal_count):
            template = random.choice(signal_templates)
            article = self._fill_template(template, {
                'city': random.choice(['Austin', 'Dallas', 'Houston', 'San Antonio']),
                'industry': random.choice(['healthcare', 'technology', 'manufacturing', 'retail']),
                'program': random.choice(['grant program', 'mentorship initiative', 'funding opportunity', 'support network']),
                'community': random.choice(['minority entrepreneurs', 'women-owned businesses', 'veteran startups', 'local innovators']),
                'district': random.choice(['downtown', 'tech district', 'innovation quarter', 'business park']),
                'type': random.choice(['technology', 'sustainable', 'social impact', 'economic']),
                'sector': random.choice(['tech', 'healthcare', 'manufacturing', 'service']),
                'project': random.choice(['sustainability', 'innovation', 'community development', 'economic growth'])
            })
            
            articles.append({
                'title': article,
                'description': f"Business and innovation news about {article.lower()}",
                'link': f"https://example.com/mixed-business/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This covers local business innovation and entrepreneurship.",
                'author': random.choice(['Business Reporter', 'Innovation News', 'Economic Development', 'Local Business']),
                'tags': ['business', 'innovation', 'entrepreneurship', 'local'],
                'expected_outcome': 'KEEP',
                'category': 'signal',
                'relevance_score_expected': random.uniform(0.4, 0.7)
            })
        
        for i in range(noise_count):
            template = random.choice(noise_templates)
            article = self._fill_template(template, {
                'name': random.choice(['Jennifer Lopez', 'Brad Pitt', 'Taylor Swift', 'Ryan Reynolds']),
                'location': random.choice(['upscale', 'trendy', 'popular', 'exclusive']),
                'film': random.choice(['Action Hero 3', 'Romance Story', 'Sci-Fi Adventure', 'Comedy Central']),
                'rating': random.choice(['poor reviews', 'mixed reactions', 'low scores', 'disappointing box office']),
                'season': random.choice(['spring', 'summer', 'fall', 'winter']),
                'style': random.choice(['bold colors', 'minimalist designs', 'vintage looks', 'casual wear']),
                'number': random.choice(['5', '10', '15', '20']),
                'region': random.choice(['Europe', 'Asia', 'South America', 'Caribbean']),
                'dish': random.choice(['chocolate chip cookies', 'banana bread', 'pasta sauce', 'grilled chicken']),
                'team': random.choice(['Lakers', 'Cowboys', 'Yankees', 'Warriors']),
                'result': random.choice(['wins', 'loses', 'ties', 'advances']),
                'sport': random.choice(['basketball', 'football', 'baseball', 'soccer']),
                'condition': random.choice(['rain', 'snow', 'sunshine', 'storms']),
                'timeframe': random.choice(['weekend', 'week', 'month', 'season']),
                'show': random.choice(['Drama Series', 'Comedy Show', 'Reality TV', 'Documentary']),
                'network': random.choice(['Netflix', 'HBO', 'Amazon Prime', 'Disney+']),
                'advice': random.choice(['exercise regularly', 'eat healthy', 'get enough sleep', 'reduce stress']),
                'aspect': random.choice(['sleep', 'nutrition', 'fitness', 'mental health']),
                'project': random.choice(['kitchen renovation', 'bathroom update', 'garden makeover', 'bedroom refresh']),
                'room': random.choice(['kitchen', 'bathroom', 'bedroom', 'living room'])
            })
            
            articles.append({
                'title': article,
                'description': f"General interest news about {article.lower()}",
                'link': f"https://example.com/mixed-general/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This covers entertainment, lifestyle, and general interest topics.",
                'author': random.choice(['Entertainment Writer', 'Lifestyle Editor', 'General Reporter', 'Feature Writer']),
                'tags': ['entertainment', 'lifestyle', 'general', 'popular'],
                'expected_outcome': 'DISCARD',
                'category': 'noise',
                'relevance_score_expected': random.uniform(0.05, 0.3)
            })
        
        return articles
    
    def generate_noise_heavy_articles(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate noise-heavy content with 5% signal, 95% noise"""
        
        signal_templates = [
            "Breaking: Major policy announcement affects local businesses in {region}",
            "Government initiative supports {industry} development with new {program}"
        ]
        
        noise_templates = [
            "Recipe: How to make perfect {dish} with {ingredient}",
            "Movie review: {film} {verdict} with {aspect}",
            "Horoscope predictions for {sign} this {period}",
            "Pet care tips for new {pet} owners",
            "Home improvement: DIY {project} for beginners",
            "Fashion: {trend} is the new must-have for {season}",
            "Travel guide: {destination} offers {attraction} for visitors",
            "Health: {benefit} of {activity} for {demographic}",
            "Food: {restaurant} serves {cuisine} in {location}",
            "Entertainment: {event} features {performer} this {timeframe}",
            "Sports: {athlete} {achievement} in {sport} competition",
            "Weather: {forecast} expected for {area} this {period}",
            "Celebrity: {star} announces {news} on social media",
            "Gaming: {game} releases {update} with new {feature}",
            "Music: {artist} drops {album} featuring {collaboration}"
        ]
        
        articles = []
        signal_count = int(count * 0.05)  # 5% signal
        noise_count = count - signal_count  # 95% noise
        
        for i in range(signal_count):
            template = random.choice(signal_templates)
            article = self._fill_template(template, {
                'region': random.choice(['North Texas', 'Central Texas', 'East Texas', 'West Texas']),
                'industry': random.choice(['technology', 'healthcare', 'manufacturing', 'agriculture']),
                'program': random.choice(['tax incentives', 'grant funding', 'regulatory changes', 'support services'])
            })
            
            articles.append({
                'title': article,
                'description': f"Important policy news about {article.lower()}",
                'link': f"https://example.com/noise-heavy-signal/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This is important policy or business news that should be kept.",
                'author': random.choice(['Policy Reporter', 'Government Affairs', 'Business News', 'Economic Analysis']),
                'tags': ['policy', 'business', 'government', 'important'],
                'expected_outcome': 'KEEP',
                'category': 'signal',
                'relevance_score_expected': random.uniform(0.5, 0.8)
            })
        
        for i in range(noise_count):
            template = random.choice(noise_templates)
            article = self._fill_template(template, {
                'dish': random.choice(['chocolate chip cookies', 'banana bread', 'pasta carbonara', 'grilled salmon']),
                'ingredient': random.choice(['organic flour', 'fresh herbs', 'premium chocolate', 'local vegetables']),
                'film': random.choice(['Action Blockbuster', 'Romantic Comedy', 'Sci-Fi Thriller', 'Horror Movie']),
                'verdict': random.choice(['impresses audiences', 'disappoints critics', 'breaks box office records', 'receives mixed reviews']),
                'aspect': random.choice(['stunning visuals', 'weak plot', 'great acting', 'poor dialogue']),
                'sign': random.choice(['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo']),
                'period': random.choice(['week', 'month', 'season', 'year']),
                'pet': random.choice(['dog', 'cat', 'bird', 'fish']),
                'project': random.choice(['kitchen renovation', 'garden makeover', 'bathroom update', 'bedroom refresh']),
                'trend': random.choice(['minimalist design', 'bold colors', 'vintage style', 'sustainable fashion']),
                'season': random.choice(['spring', 'summer', 'fall', 'winter']),
                'destination': random.choice(['Paris', 'Tokyo', 'New York', 'London']),
                'attraction': random.choice(['museums', 'restaurants', 'shopping', 'nightlife']),
                'benefit': random.choice(['health benefits', 'mental wellness', 'physical fitness', 'stress relief']),
                'activity': random.choice(['yoga', 'meditation', 'running', 'swimming']),
                'demographic': random.choice(['seniors', 'young adults', 'families', 'professionals']),
                'restaurant': random.choice(['Bistro 21', 'The Garden Cafe', 'Urban Kitchen', 'Coastal Grill']),
                'cuisine': random.choice(['Italian', 'Mexican', 'Asian', 'Mediterranean']),
                'location': random.choice(['downtown', 'uptown', 'midtown', 'suburbs']),
                'event': random.choice(['Music Festival', 'Art Exhibition', 'Food Fair', 'Cultural Celebration']),
                'performer': random.choice(['local band', 'famous artist', 'dance troupe', 'theater group']),
                'timeframe': random.choice(['weekend', 'month', 'season', 'year']),
                'athlete': random.choice(['Tom Brady', 'Serena Williams', 'LeBron James', 'Cristiano Ronaldo']),
                'achievement': random.choice(['wins championship', 'breaks record', 'announces retirement', 'signs contract']),
                'sport': random.choice(['football', 'tennis', 'basketball', 'soccer']),
                'forecast': random.choice(['sunny weather', 'rainy conditions', 'snow storms', 'clear skies']),
                'area': random.choice(['North Texas', 'DFW area', 'Central Texas', 'Houston area']),
                'star': random.choice(['Taylor Swift', 'Ryan Reynolds', 'Jennifer Lopez', 'Chris Evans']),
                'news': random.choice(['new project', 'engagement', 'charity work', 'business venture']),
                'game': random.choice(['Call of Duty', 'Fortnite', 'Minecraft', 'FIFA']),
                'update': random.choice(['major update', 'patch', 'expansion', 'DLC']),
                'feature': random.choice(['multiplayer mode', 'graphics engine', 'character customization', 'storyline']),
                'artist': random.choice(['Drake', 'Taylor Swift', 'The Weeknd', 'Billie Eilish']),
                'album': random.choice(['new album', 'surprise EP', 'greatest hits', 'remix collection']),
                'collaboration': random.choice(['guest vocals', 'producer credits', 'featured artist', 'duet'])
            })
            
            articles.append({
                'title': article,
                'description': f"General interest content about {article.lower()}",
                'link': f"https://example.com/noise-heavy-general/{uuid.uuid4()}",
                'published': self._random_date(),
                'content': f"Full article content about {article}. This is entertainment, lifestyle, or general interest content that should be discarded.",
                'author': random.choice(['Lifestyle Writer', 'Entertainment Reporter', 'General Interest', 'Popular Culture']),
                'tags': ['entertainment', 'lifestyle', 'popular', 'general'],
                'expected_outcome': 'DISCARD',
                'category': 'noise',
                'relevance_score_expected': random.uniform(0.01, 0.2)
            })
        
        return articles
    
    def _fill_template(self, template: str, replacements: Dict[str, str]) -> str:
        """Fill template with random replacements"""
        result = template
        for key, value in replacements.items():
            result = result.replace(f"{{{key}}}", value)
        return result
    
    def _random_date(self) -> datetime:
        """Generate random date within last 30 days"""
        days_ago = random.randint(0, 30)
        return self.base_date + timedelta(days=days_ago)
    
    def generate_test_dataset(self) -> Dict[str, Any]:
        """Generate complete test dataset with all categories"""
        
        print("Generating test dataset...")
        
        dataset = {
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'total_articles': 400,
                'categories': {
                    'fort_worth_political': {'count': 100, 'signal_ratio': 0.85},
                    'tech_startups': {'count': 100, 'signal_ratio': 0.60},
                    'mixed_content': {'count': 100, 'signal_ratio': 0.25},
                    'noise_heavy': {'count': 100, 'signal_ratio': 0.05}
                }
            },
            'articles': {
                'fort_worth_political': self.generate_fort_worth_political_articles(100),
                'tech_startups': self.generate_tech_startup_articles(100),
                'mixed_content': self.generate_mixed_content_articles(100),
                'noise_heavy': self.generate_noise_heavy_articles(100)
            }
        }
        
        all_articles = []
        for category_articles in dataset['articles'].values():
            all_articles.extend(category_articles)
        
        total_signal = len([a for a in all_articles if a['expected_outcome'] == 'KEEP'])
        total_noise = len([a for a in all_articles if a['expected_outcome'] == 'DISCARD'])
        
        dataset['metadata']['overall_stats'] = {
            'total_signal': total_signal,
            'total_noise': total_noise,
            'signal_ratio': total_signal / len(all_articles),
            'noise_ratio': total_noise / len(all_articles)
        }
        
        print(f"Generated {len(all_articles)} articles:")
        print(f"  - Signal (KEEP): {total_signal} ({total_signal/len(all_articles)*100:.1f}%)")
        print(f"  - Noise (DISCARD): {total_noise} ({total_noise/len(all_articles)*100:.1f}%)")
        
        return dataset
    
    def save_dataset(self, dataset: Dict[str, Any], filename: str = "test_dataset.json"):
        """Save dataset to JSON file"""
        with open(filename, 'w') as f:
            json.dump(dataset, f, indent=2, default=str)
        print(f"Dataset saved to {filename}")
    
    def create_rss_feeds(self, dataset: Dict[str, Any]) -> Dict[str, str]:
        """Create RSS feed XML files from dataset"""
        
        rss_feeds = {}
        
        for category, articles in dataset['articles'].items():
            rss_xml = self._create_rss_xml(category, articles)
            filename = f"test_rss_{category}.xml"
            
            with open(filename, 'w') as f:
                f.write(rss_xml)
            
            rss_feeds[category] = filename
            print(f"Created RSS feed: {filename}")
        
        return rss_feeds
    
    def _create_rss_xml(self, category: str, articles: List[Dict[str, Any]]) -> str:
        """Create RSS XML from articles"""
        
        category_titles = {
            'fort_worth_political': 'Fort Worth Political News',
            'tech_startups': 'Tech Startup News',
            'mixed_content': 'Mixed Content News',
            'noise_heavy': 'General Interest News'
        }
        
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{category_titles.get(category, category.title())}</title>
    <description>Test RSS feed for {category} articles</description>
    <link>https://example.com/{category}</link>
    <lastBuildDate>{datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
'''
        
        for article in articles:
            pub_date = article['published'].strftime('%a, %d %b %Y %H:%M:%S GMT')
            xml += f'''
    <item>
      <title><![CDATA[{article['title']}]]></title>
      <description><![CDATA[{article['description']}]]></description>
      <link>{article['link']}</link>
      <pubDate>{pub_date}</pubDate>
      <author>{article['author']}</author>
      <guid>{article['link']}</guid>
    </item>'''
        
        xml += '''
  </channel>
</rss>'''
        
        return xml


if __name__ == "__main__":
    generator = TestRSSGenerator()
    dataset = generator.generate_test_dataset()
    generator.save_dataset(dataset)
    rss_feeds = generator.create_rss_feeds(dataset)
    
    print("\nTest data generation complete!")
    print(f"Dataset: test_dataset.json")
    print(f"RSS feeds: {list(rss_feeds.values())}")
