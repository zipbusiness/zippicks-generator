"""
Schema Builder - Generates JSON-LD structured data for SEO
"""

from typing import Dict, List
from datetime import datetime
import json
import yaml
from pathlib import Path


class SchemaBuilder:
    """Generates schema.org structured data for restaurant lists"""
    
    def __init__(self):
        self.base_context = "https://schema.org"
        self._load_city_config()
        
    def _load_city_config(self):
        """Load city configuration from YAML file"""
        config_path = Path("config/cities.yaml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.cities = config.get('cities', {})
        else:
            self.cities = {}
            
    def generate_restaurant_list_schema(self, restaurants: List[Dict], city: str, vibe: str) -> Dict:
        """Generate ItemList schema for the entire restaurant list"""
        
        # Create the main ItemList
        schema = {
            "@context": self.base_context,
            "@type": "ItemList",
            "name": f"Top 10 {vibe} Restaurants in {city}",
            "description": f"Expert-curated list of the best {vibe.lower()} restaurants in {city}, featuring local favorites and hidden gems.",
            "numberOfItems": len(restaurants),
            "itemListElement": []
        }
        
        # Add each restaurant as a ListItem
        for restaurant in restaurants:
            list_item = {
                "@type": "ListItem",
                "position": restaurant['rank'],
                "item": self.generate_restaurant_schema(restaurant, city)
            }
            schema["itemListElement"].append(list_item)
        
        # Add additional metadata
        schema["url"] = f"https://zippicks.com/{city.lower().replace(' ', '-')}/{vibe.lower().replace(' ', '-')}-restaurants"
        schema["datePublished"] = datetime.now().isoformat()
        schema["dateModified"] = datetime.now().isoformat()
        
        # Add author/publisher
        schema["author"] = {
            "@type": "Organization",
            "name": "ZipPicks",
            "url": "https://zippicks.com"
        }
        
        return schema
    
    def generate_restaurant_schema(self, restaurant: Dict, city: str) -> Dict:
        """Generate schema for individual restaurant"""
        
        schema = {
            "@context": self.base_context,
            "@type": "Restaurant",
            "name": restaurant['name'],
            "description": restaurant.get('why_perfect', ''),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": restaurant['address'],
                "addressLocality": city,
                "addressCountry": "US"
            },
            "priceRange": restaurant['price_range']
        }
        
        # Add serves cuisine based on must-try item
        if restaurant.get('must_try'):
            schema["servesCuisine"] = self._extract_cuisine(restaurant['must_try'])
        
        # Add aggregate rating if available
        if restaurant.get('rating'):
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": restaurant['rating'],
                "bestRating": "5",
                "worstRating": "1"
            }
            
            if restaurant.get('review_count'):
                schema["aggregateRating"]["reviewCount"] = restaurant['review_count']
        
        # Add URL if available
        if restaurant.get('url'):
            schema["url"] = restaurant['url']
        
        # Add telephone if available
        if restaurant.get('phone'):
            schema["telephone"] = restaurant['phone']
        
        # Add opening hours if available
        if restaurant.get('hours'):
            schema["openingHours"] = restaurant['hours']
        
        # Add amenities based on vibe
        schema["amenityFeature"] = self._get_amenities(restaurant)
        
        # Add review snippet
        if restaurant.get('why_perfect'):
            schema["review"] = {
                "@type": "Review",
                "reviewBody": restaurant['why_perfect'],
                "author": {
                    "@type": "Organization",
                    "name": "ZipPicks Editorial Team"
                },
                "datePublished": datetime.now().isoformat(),
                "reviewRating": {
                    "@type": "Rating",
                    "ratingValue": "5",
                    "bestRating": "5"
                }
            }
        
        return schema
    
    def generate_webpage_schema(self, data: Dict) -> Dict:
        """Generate WebPage schema for the entire article"""
        
        schema = {
            "@context": self.base_context,
            "@type": "WebPage",
            "name": f"Top 10 {data['vibe_title']} Restaurants in {data['city_title']} - ZipPicks",
            "description": f"Discover the best {data['vibe_title'].lower()} restaurants in {data['city_title']}. Expert reviews, must-try dishes, and local recommendations.",
            "url": f"https://zippicks.com/{data['city']}/{data['vibe']}-restaurants",
            "datePublished": data.get('validated_at', datetime.now().isoformat()),
            "dateModified": datetime.now().isoformat(),
            "publisher": {
                "@type": "Organization",
                "name": "ZipPicks",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://zippicks.com/logo.png"
                }
            },
            "breadcrumb": {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": "https://zippicks.com"
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": data['city_title'],
                        "item": f"https://zippicks.com/{data['city']}"
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": f"{data['vibe_title']} Restaurants",
                        "item": f"https://zippicks.com/{data['city']}/{data['vibe']}-restaurants"
                    }
                ]
            }
        }
        
        # Add main entity (the restaurant list)
        schema["mainEntity"] = self.generate_restaurant_list_schema(
            data['restaurants'],
            data['city_title'],
            data['vibe_title']
        )
        
        return schema
    
    def generate_local_business_schema(self, city: str, vibe: str) -> Dict:
        """Generate LocalBusiness schema for local SEO"""
        
        schema = {
            "@context": self.base_context,
            "@type": "LocalBusiness",
            "name": f"ZipPicks {city} Restaurant Guide",
            "description": f"Your trusted source for the best {vibe.lower()} restaurants in {city}",
            "url": f"https://zippicks.com/{city.lower().replace(' ', '-')}",
            "@id": f"https://zippicks.com/{city.lower().replace(' ', '-')}#organization",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": city,
                "addressCountry": "US"
            },
            "geo": self._get_city_coordinates(city),
            "areaServed": {
                "@type": "City",
                "name": city
            }
        }
        
        return schema
    
    def _extract_cuisine(self, must_try: str) -> str:
        """Extract cuisine type from must-try dish"""
        
        must_try_lower = must_try.lower()
        
        # Cuisine mapping
        cuisine_map = {
            'italian': ['pasta', 'pizza', 'risotto', 'italian', 'ravioli', 'gnocchi'],
            'japanese': ['sushi', 'ramen', 'tempura', 'japanese', 'sake', 'udon'],
            'mexican': ['taco', 'burrito', 'mexican', 'margarita', 'enchilada', 'quesadilla'],
            'american': ['burger', 'steak', 'bbq', 'american', 'wings', 'ribs'],
            'french': ['french', 'croissant', 'crepe', 'bistro', 'wine', 'champagne'],
            'chinese': ['chinese', 'dim sum', 'wonton', 'noodle', 'dumpling', 'peking'],
            'thai': ['thai', 'pad thai', 'curry', 'tom yum', 'satay'],
            'indian': ['indian', 'curry', 'tikka', 'naan', 'biryani', 'tandoori'],
            'mediterranean': ['mediterranean', 'greek', 'hummus', 'falafel', 'mezze'],
            'seafood': ['seafood', 'fish', 'oyster', 'lobster', 'crab', 'shrimp']
        }
        
        for cuisine, keywords in cuisine_map.items():
            if any(keyword in must_try_lower for keyword in keywords):
                return cuisine.title()
        
        return "Contemporary"
    
    def _get_amenities(self, restaurant: Dict) -> List[Dict]:
        """Get restaurant amenities based on vibe and description"""
        
        amenities = []
        
        # Check description for amenity keywords
        description = restaurant.get('why_perfect', '').lower()
        
        amenity_map = {
            'Outdoor Seating': ['outdoor', 'patio', 'terrace', 'garden', 'rooftop'],
            'Romantic Atmosphere': ['romantic', 'intimate', 'candlelit', 'cozy', 'date'],
            'Family Friendly': ['family', 'kids', 'children', 'high chair'],
            'Late Night Service': ['late night', 'midnight', 'after hours', '24 hour'],
            'Live Music': ['live music', 'jazz', 'piano', 'band', 'performance'],
            'Private Dining': ['private', 'event', 'party room', 'celebration'],
            'Bar Service': ['bar', 'cocktail', 'wine', 'beer', 'drinks'],
            'Valet Parking': ['valet', 'parking service'],
            'Reservations Recommended': ['reservation', 'book ahead', 'popular']
        }
        
        for amenity, keywords in amenity_map.items():
            if any(keyword in description for keyword in keywords):
                amenities.append({
                    "@type": "LocationFeatureSpecification",
                    "name": amenity,
                    "value": True
                })
        
        return amenities
    
    def _get_city_coordinates(self, city: str) -> Dict:
        """Get approximate coordinates for major cities from config"""
        
        # Find city in config (handle various formats)
        city_key = None
        for key, city_data in self.cities.items():
            if city_data.get('name', '').lower() == city.lower():
                city_key = key
                break
        
        # Get coordinates from config or use US center as default
        default_coords = {'latitude': 39.8283, 'longitude': -98.5795}
        
        if city_key and 'coordinates' in self.cities[city_key]:
            coords = self.cities[city_key]['coordinates']
        else:
            coords = default_coords
        
        return {
            "@type": "GeoCoordinates",
            "latitude": coords['latitude'],
            "longitude": coords['longitude']
        }
    
    def generate_faq_schema(self, city: str, vibe: str) -> Dict:
        """Generate FAQ schema for common questions"""
        
        faqs = {
            'date-night': [
                {
                    "question": f"What are the most romantic restaurants in {city}?",
                    "answer": f"Our top picks for romantic dining in {city} include upscale establishments with intimate atmospheres, candlelit settings, and exceptional service perfect for special occasions."
                },
                {
                    "question": f"Do I need reservations for date night restaurants in {city}?",
                    "answer": f"Yes, we highly recommend making reservations for popular date night spots in {city}, especially on weekends. Many of these restaurants book up quickly."
                }
            ],
            'family-friendly': [
                {
                    "question": f"Which {city} restaurants have kids menus?",
                    "answer": f"All of our recommended family-friendly restaurants in {city} offer dedicated kids menus with favorites like chicken fingers, pasta, and grilled cheese."
                },
                {
                    "question": f"Do these restaurants have high chairs available?",
                    "answer": f"Yes, every restaurant on our family-friendly list provides high chairs and booster seats for young diners."
                }
            ],
            'quick-lunch': [
                {
                    "question": f"How fast is service at these {city} lunch spots?",
                    "answer": f"Most restaurants on our quick lunch list can serve your meal within 15-20 minutes, perfect for busy lunch breaks."
                },
                {
                    "question": f"Do these restaurants offer takeout?",
                    "answer": f"Yes, all of our recommended quick lunch spots in {city} offer takeout options for even faster service."
                }
            ]
        }
        
        questions = faqs.get(vibe, [
            {
                "question": f"What makes these the best {vibe} restaurants in {city}?",
                "answer": f"We select restaurants based on atmosphere, food quality, service, and how well they match the {vibe} dining experience."
            }
        ])
        
        schema = {
            "@context": self.base_context,
            "@type": "FAQPage",
            "mainEntity": []
        }
        
        for faq in questions:
            schema["mainEntity"].append({
                "@type": "Question",
                "name": faq["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq["answer"]
                }
            })
        
        return schema
    
    def combine_schemas(self, schemas: List[Dict]) -> List[Dict]:
        """Combine multiple schema objects using @graph"""
        
        return {
            "@context": self.base_context,
            "@graph": schemas
        }


if __name__ == "__main__":
    # Test schema generation
    builder = SchemaBuilder()
    
    # Test data
    test_restaurants = [
        {
            'rank': 1,
            'name': 'The Romantic Bistro',
            'why_perfect': 'Intimate candlelit atmosphere perfect for special occasions.',
            'must_try': 'Pan-seared duck with cherry reduction',
            'address': '123 Main St, San Francisco, CA 94102',
            'price_range': '$$$',
            'rating': 4.8,
            'review_count': 245
        }
    ]
    
    # Generate schemas
    list_schema = builder.generate_restaurant_list_schema(test_restaurants, "San Francisco", "Date Night")
    faq_schema = builder.generate_faq_schema("San Francisco", "date-night")
    
    # Combine schemas
    combined = builder.combine_schemas([list_schema, faq_schema])
    
    print("Generated Schema:")
    print(json.dumps(combined, indent=2))