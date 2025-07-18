"""
Response Validator - Validates Claude responses for structure and quality
"""

import re
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class ResponseValidator:
    """Validates Claude responses for structure and quality"""
    
    def __init__(self):
        self.required_fields = ['name', 'why_perfect', 'must_try', 'address', 'price_range']
        self.price_ranges = ['$', '$$', '$$$', '$$$$']
        
    def validate_response(self, response: str, city: str, vibe: str) -> Dict:
        """
        Validate a Claude response for correctness
        
        Returns:
            Dict with keys:
            - valid: bool
            - errors: List[str]
            - parsed_data: Dict (if valid)
            - restaurant_count: int
        """
        
        result = {
            'valid': True,
            'errors': [],
            'parsed_data': None,
            'restaurant_count': 0
        }
        
        try:
            # 1. Parse the response
            parsed = self.parse_claude_response(response)
            
            # 2. Check basic structure
            if 'restaurants' not in parsed or not isinstance(parsed['restaurants'], list):
                result['errors'].append("Could not parse restaurant list from response")
                result['valid'] = False
                return result
            
            restaurants = parsed['restaurants']
            result['restaurant_count'] = len(restaurants)
            
            # 3. Validate restaurant count
            if len(restaurants) != 10:
                result['errors'].append(f"Expected 10 restaurants, got {len(restaurants)}")
                result['valid'] = False
            elif len(restaurants) == 0:
                result['errors'].append("No restaurants found in response")
                result['valid'] = False
                return result
            
            # 4. Check for duplicates
            names = [r.get('name', '').lower().strip() for r in restaurants]
            unique_names = set(names)
            if len(names) != len(unique_names):
                duplicates = [name for name in names if names.count(name) > 1]
                result['errors'].append(f"Duplicate restaurant names found: {', '.join(set(duplicates))}")
                result['valid'] = False
            
            # 5. Validate each restaurant
            for i, restaurant in enumerate(restaurants, 1):
                errors = self.validate_restaurant(restaurant, i)
                if errors:
                    result['errors'].extend(errors)
                    result['valid'] = False
            
            # 6. Validate ranking sequence
            ranks = [r.get('rank', 0) for r in restaurants]
            expected_ranks = list(range(1, len(restaurants) + 1))
            if ranks != expected_ranks:
                result['errors'].append(f"Invalid ranking sequence. Expected {expected_ranks}, got {ranks}")
                result['valid'] = False
            
            # 7. Check vibe relevance (warning only)
            vibe_check = self.validate_vibe_relevance(restaurants, vibe)
            if not vibe_check['relevant']:
                result['warnings'] = result.get('warnings', [])
                result['warnings'].append(f"Low vibe relevance: {vibe_check['message']}")
            
            # If valid, add metadata
            if result['valid']:
                parsed['city'] = city
                parsed['vibe'] = vibe
                parsed['validated_at'] = datetime.now().isoformat()
                parsed['city_title'] = city.replace('-', ' ').title()
                parsed['vibe_title'] = vibe.replace('-', ' ').title()
                result['parsed_data'] = parsed
                
        except Exception as e:
            result['errors'].append(f"Parse error: {str(e)}")
            result['valid'] = False
        
        return result
    
    def parse_claude_response(self, response: str) -> Dict:
        """Parse Claude's response into structured data"""
        
        restaurants = []
        
        # Clean response
        response = response.strip()
        
        # Try multiple parsing strategies
        restaurants = self._parse_numbered_format(response)
        
        if not restaurants:
            restaurants = self._parse_header_format(response)
        
        if not restaurants:
            restaurants = self._parse_markdown_format(response)
        
        return {'restaurants': restaurants}
    
    def _parse_numbered_format(self, response: str) -> List[Dict]:
        """Parse numbered list format (most common)"""
        restaurants = []
        
        # Pattern for numbered entries with bold or without
        patterns = [
            # **1. Restaurant Name** format
            r'\*\*(\d+)\.\s+([^*\n]+)\*\*\s*\n\s*-?\s*Why:?\s*([^\n]+(?:\n(?!-).*)?)\n\s*-?\s*Must-try:?\s*([^\n]+)\n\s*-?\s*Address:?\s*([^\n]+)\n\s*-?\s*Price:?\s*([^\n]+)',
            
            # 1. Restaurant Name format (no bold)
            r'^(\d+)\.\s+([^\n]+)\n\s*-?\s*Why:?\s*([^\n]+(?:\n(?!-).*)?)\n\s*-?\s*Must-try:?\s*([^\n]+)\n\s*-?\s*Address:?\s*([^\n]+)\n\s*-?\s*Price:?\s*([^\n]+)',
            
            # With bullet points
            r'(\d+)\.\s+([^\n]+)\n\s*•\s*Why:?\s*([^\n]+(?:\n(?!•).*)?)\n\s*•\s*Must-try:?\s*([^\n]+)\n\s*•\s*Address:?\s*([^\n]+)\n\s*•\s*Price:?\s*([^\n]+)'
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, response, re.MULTILINE | re.IGNORECASE))
            
            if matches:
                for match in matches:
                    restaurant = {
                        'rank': int(match.group(1)),
                        'name': match.group(2).strip().strip('*'),
                        'why_perfect': self._clean_text(match.group(3)),
                        'must_try': self._clean_text(match.group(4)),
                        'address': self._clean_text(match.group(5)),
                        'price_range': self.normalize_price(match.group(6).strip())
                    }
                    restaurants.append(restaurant)
                break
        
        return restaurants
    
    def _parse_header_format(self, response: str) -> List[Dict]:
        """Parse header-based format (### 1. Restaurant)"""
        restaurants = []
        
        # Split by headers
        sections = re.split(r'###?\s*(\d+)\.\s*([^\n]+)', response)
        
        if len(sections) > 1:
            # Process in groups of 3 (separator, number, name, content)
            for i in range(1, len(sections), 3):
                if i + 2 < len(sections):
                    rank = int(sections[i])
                    name = sections[i + 1].strip()
                    content = sections[i + 2] if i + 2 < len(sections) else ""
                    
                    # Parse content for fields
                    restaurant = self._parse_restaurant_content(content)
                    restaurant['rank'] = rank
                    restaurant['name'] = name
                    
                    if self._is_valid_restaurant(restaurant):
                        restaurants.append(restaurant)
        
        return restaurants
    
    def _parse_markdown_format(self, response: str) -> List[Dict]:
        """Parse various markdown formats"""
        restaurants = []
        
        # Try to split by double newlines first
        blocks = response.split('\n\n')
        
        for block in blocks:
            # Check if this looks like a restaurant entry
            if re.match(r'^\d+\.', block.strip()):
                restaurant = self._parse_restaurant_block(block)
                if restaurant and self._is_valid_restaurant(restaurant):
                    restaurants.append(restaurant)
        
        return restaurants
    
    def _parse_restaurant_block(self, block: str) -> Optional[Dict]:
        """Parse a single restaurant block"""
        lines = block.strip().split('\n')
        
        if not lines:
            return None
        
        # Parse first line for rank and name
        first_line = lines[0]
        match = re.match(r'^(\d+)\.\s*(.+)', first_line)
        
        if not match:
            return None
        
        restaurant = {
            'rank': int(match.group(1)),
            'name': match.group(2).strip().strip('*'),
            'why_perfect': '',
            'must_try': '',
            'address': '',
            'price_range': '$'
        }
        
        # Parse remaining lines
        current_field = None
        
        for line in lines[1:]:
            line = line.strip()
            
            if not line:
                continue
            
            # Check for field markers
            if any(marker in line.lower() for marker in ['why:', '- why:', '• why:', 'why it']):
                current_field = 'why_perfect'
                value = re.sub(r'^[-•]\s*(why:?|why it[^:]*:?)\s*', '', line, flags=re.IGNORECASE)
                restaurant[current_field] = value
            elif any(marker in line.lower() for marker in ['must-try:', 'must try:', '- must', '• must']):
                current_field = 'must_try'
                value = re.sub(r'^[-•]\s*(must[- ]try:?)\s*', '', line, flags=re.IGNORECASE)
                restaurant[current_field] = value
            elif any(marker in line.lower() for marker in ['address:', '- address:', '• address:']):
                current_field = 'address'
                value = re.sub(r'^[-•]\s*(address:?)\s*', '', line, flags=re.IGNORECASE)
                restaurant[current_field] = value
            elif any(marker in line.lower() for marker in ['price:', '- price:', '• price:']):
                current_field = 'price_range'
                value = re.sub(r'^[-•]\s*(price:?)\s*', '', line, flags=re.IGNORECASE)
                restaurant[current_field] = self.normalize_price(value)
            elif current_field and line.startswith(' '):
                # Continuation of previous field
                restaurant[current_field] += ' ' + line
            elif current_field == 'why_perfect' and not any(marker in line.lower() for marker in ['must', 'address', 'price']):
                # Continuation of why_perfect on new line
                restaurant[current_field] += ' ' + line
        
        return restaurant
    
    def _parse_restaurant_content(self, content: str) -> Dict:
        """Parse restaurant content section for fields"""
        restaurant = {
            'why_perfect': '',
            'must_try': '',
            'address': '',
            'price_range': '$'
        }
        
        # Try to extract each field
        why_match = re.search(r'Why:?\s*([^\n]+(?:\n(?!(?:Must-try|Address|Price)).*)*)', content, re.IGNORECASE)
        if why_match:
            restaurant['why_perfect'] = self._clean_text(why_match.group(1))
        
        must_match = re.search(r'Must[- ]try:?\s*([^\n]+)', content, re.IGNORECASE)
        if must_match:
            restaurant['must_try'] = self._clean_text(must_match.group(1))
        
        address_match = re.search(r'Address:?\s*([^\n]+)', content, re.IGNORECASE)
        if address_match:
            restaurant['address'] = self._clean_text(address_match.group(1))
        
        price_match = re.search(r'Price:?\s*([^\n]+)', content, re.IGNORECASE)
        if price_match:
            restaurant['price_range'] = self.normalize_price(price_match.group(1))
        
        return restaurant
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        if not text:
            return ""
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove leading bullets or dashes
        text = re.sub(r'^[-•]\s*', '', text)
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove trailing punctuation from field markers
        text = re.sub(r'^(Why|Must[- ]try|Address|Price):?\s*', '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _is_valid_restaurant(self, restaurant: Dict) -> bool:
        """Check if restaurant has minimum required fields"""
        return (
            restaurant.get('name') and 
            restaurant.get('why_perfect') and 
            len(restaurant.get('why_perfect', '')) > 10
        )
    
    def validate_restaurant(self, restaurant: Dict, index: int) -> List[str]:
        """Validate individual restaurant entry"""
        errors = []
        
        # Check required fields
        for field in self.required_fields:
            if field not in restaurant or not restaurant[field]:
                errors.append(f"Restaurant #{index}: Missing {field}")
            elif field == 'price_range' and restaurant[field] not in self.price_ranges:
                errors.append(f"Restaurant #{index}: Invalid price range '{restaurant[field]}' (must be $, $$, $$$, or $$$$)")
        
        # Validate field content quality
        if restaurant.get('why_perfect'):
            why_len = len(restaurant['why_perfect'])
            if why_len < 20:
                errors.append(f"Restaurant #{index}: 'Why perfect' too short ({why_len} chars, need 20+)")
            elif why_len > 500:
                errors.append(f"Restaurant #{index}: 'Why perfect' too long ({why_len} chars, max 500)")
        
        if restaurant.get('must_try'):
            must_len = len(restaurant['must_try'])
            if must_len < 5:
                errors.append(f"Restaurant #{index}: 'Must try' too short ({must_len} chars, need 5+)")
            elif must_len > 100:
                errors.append(f"Restaurant #{index}: 'Must try' too long ({must_len} chars, max 100)")
        
        # Validate address format
        if restaurant.get('address'):
            address = restaurant['address']
            # Basic address validation - should have numbers and commas
            if not re.search(r'\d', address):
                errors.append(f"Restaurant #{index}: Address missing street number")
            if ',' not in address and len(address.split()) < 4:
                errors.append(f"Restaurant #{index}: Address may be incomplete (no comma found)")
        
        # Check for placeholder text
        if restaurant.get('name'):
            if 'restaurant name' in restaurant['name'].lower():
                errors.append(f"Restaurant #{index}: Name contains placeholder text")
        
        return errors
    
    def normalize_price(self, price: str) -> str:
        """Normalize price range to standard format"""
        if not price:
            return '$'
        
        # Remove all non-dollar characters
        dollars = re.findall(r'\$+', price)
        
        if dollars:
            # Take the first dollar sequence found
            dollar_str = dollars[0]
            count = len(dollar_str)
            
            if count > 4:
                return '$$$$'
            elif count > 0:
                return dollar_str
        
        # If no dollars found, count words
        price_lower = price.lower()
        if any(word in price_lower for word in ['expensive', 'high', 'pricey', 'upscale']):
            return '$$$'
        elif any(word in price_lower for word in ['moderate', 'medium', 'reasonable']):
            return '$$'
        elif any(word in price_lower for word in ['cheap', 'budget', 'affordable', 'inexpensive']):
            return '$'
        
        # Default
        return '$'
    
    def validate_vibe_relevance(self, restaurants: List[Dict], vibe: str) -> Dict:
        """Check that restaurants match the vibe"""
        
        vibe_keywords = {
            'date-night': ['romantic', 'intimate', 'cozy', 'candlelit', 'special', 'ambiance', 'atmosphere', 'couples', 'wine', 'dim'],
            'family-friendly': ['kids', 'family', 'casual', 'spacious', 'friendly', 'children', 'comfortable', 'relaxed', 'menu', 'high chair'],
            'quick-lunch': ['fast', 'quick', 'lunch', 'convenient', 'efficient', 'casual', 'takeout', 'grab', 'speedy', 'sandwich'],
            'trendy-vibes': ['trendy', 'hip', 'modern', 'instagram', 'stylish', 'cool', 'popular', 'scene', 'contemporary', 'chic'],
            'late-night': ['late', 'night', 'open late', '24', 'midnight', 'after hours', 'nocturnal', 'evening', 'bar', 'drinks'],
            'hidden-gems': ['hidden', 'gem', 'local', 'secret', 'discovery', 'authentic', 'neighborhood', 'unassuming', 'surprise', 'find'],
            'outdoor-dining': ['outdoor', 'patio', 'terrace', 'garden', 'al fresco', 'sidewalk', 'rooftop', 'outside', 'open-air', 'courtyard']
        }
        
        keywords = vibe_keywords.get(vibe, [])
        
        if not keywords:
            # Unknown vibe, can't validate
            return {'relevant': True, 'message': 'Unknown vibe type'}
        
        # Check how many restaurants mention vibe keywords
        matches = 0
        for restaurant in restaurants:
            why_perfect = restaurant.get('why_perfect', '').lower()
            name = restaurant.get('name', '').lower()
            
            # Check if any keyword appears
            if any(keyword in why_perfect or keyword in name for keyword in keywords):
                matches += 1
        
        # Calculate relevance
        relevance_ratio = matches / len(restaurants) if restaurants else 0
        
        if relevance_ratio >= 0.7:
            return {'relevant': True, 'message': f'High vibe relevance ({matches}/{len(restaurants)} restaurants match)'}
        elif relevance_ratio >= 0.5:
            return {'relevant': True, 'message': f'Moderate vibe relevance ({matches}/{len(restaurants)} restaurants match)'}
        else:
            return {'relevant': False, 'message': f'Low vibe relevance ({matches}/{len(restaurants)} restaurants match)'}
    
    def generate_validation_report(self, validation_results: List[Dict]) -> str:
        """Generate a summary report of validation results"""
        
        total = len(validation_results)
        valid = sum(1 for r in validation_results if r['valid'])
        
        report = f"""
VALIDATION REPORT
================
Total Processed: {total}
Valid: {valid} ({valid/total*100:.1f}% if total > 0 else 0)
Failed: {total - valid}

"""
        
        if total == 0:
            report += "No results to report.\n"
            return report
        
        # Aggregate errors
        error_counts = {}
        for result in validation_results:
            for error in result.get('errors', []):
                # Extract error type
                if ':' in error:
                    error_type = error.split(':', 1)[0]
                else:
                    error_type = error
                    
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        if error_counts:
            report += "Common Errors:\n"
            for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                report += f"- {error_type}: {count} occurrences\n"
        
        # Add success examples
        valid_results = [r for r in validation_results if r['valid']]
        if valid_results:
            report += f"\nSuccessful Validations: {len(valid_results)}\n"
            for r in valid_results[:3]:
                report += f"- {r.get('city', 'Unknown')}/{r.get('vibe', 'Unknown')}: {r.get('restaurant_count', 0)} restaurants\n"
        
        return report


# Helper function for testing
def validate_sample_response():
    """Test the validator with a sample response"""
    
    sample_response = """**1. The French Laundry**
- Why: This legendary three-Michelin-starred restaurant offers an unparalleled romantic experience with its intimate garden setting and exquisite tasting menus that create memories to last a lifetime.
- Must-try: Chef's Tasting Menu with wine pairing
- Address: 6640 Washington St, Yountville, CA 94599
- Price: $$$$

**2. Chez Panisse**
- Why: Alice Waters' iconic restaurant provides a cozy, candlelit atmosphere perfect for intimate conversations, featuring seasonal California ingredients prepared with French technique.
- Must-try: Café upstairs for casual romance, or prix fixe dinner downstairs
- Address: 1517 Shattuck Ave, Berkeley, CA 94709
- Price: $$$"""
    
    validator = ResponseValidator()
    result = validator.validate_response(sample_response, "san-francisco", "date-night")
    
    print("Validation Result:")
    print(f"Valid: {result['valid']}")
    print(f"Restaurant Count: {result['restaurant_count']}")
    
    if result['errors']:
        print("\nErrors:")
        for error in result['errors']:
            print(f"- {error}")
    
    if result.get('warnings'):
        print("\nWarnings:")
        for warning in result['warnings']:
            print(f"- {warning}")
    
    if result['valid'] and result['parsed_data']:
        print("\nParsed restaurants:")
        for r in result['parsed_data']['restaurants']:
            print(f"{r['rank']}. {r['name']} - {r['price_range']}")


if __name__ == "__main__":
    validate_sample_response()