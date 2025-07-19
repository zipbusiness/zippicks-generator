#!/usr/bin/env python3
"""
Test Unicode handling functionality
"""

from utils.unicode_handler import clean_unicode_text, sanitize_filename

def test_unicode_cleaning():
    """Test Unicode text cleaning"""
    print("Testing Unicode text cleaning...")
    
    test_cases = [
        # (input, expected_output, description)
        ("Café Naïve", "Cafe Naive", "Accented characters"),
        ("Restaurant 🍕🍔🌮", "Restaurant ", "Emoji handling"),
        ("中文餐厅", "中文餐厅", "Chinese characters"),
        ("日本料理", "日本料理", "Japanese characters"),
        ("한국음식", "한국음식", "Korean characters"),
        ("Restaurant™", "RestaurantTM", "Special symbols"),
        ("Price: €50 / £40", "Price: EUR50 / GBP40", "Currency symbols"),
        ("Multiple   spaces", "Multiple spaces", "Multiple spaces"),
        ("  Leading/trailing  ", "Leading/trailing", "Leading/trailing spaces"),
    ]
    
    for input_text, expected, description in test_cases:
        result = clean_unicode_text(input_text)
        status = "✓" if result == expected else "✗"
        print(f"{status} {description}: '{input_text}' → '{result}'")
        if result != expected:
            print(f"   Expected: '{expected}'")

def test_filename_sanitization():
    """Test filename sanitization"""
    print("\nTesting filename sanitization...")
    
    test_cases = [
        # (input, expected_output, description)
        ("café_restaurant.txt", "cafe_restaurant.txt", "Accented filename"),
        ("file with spaces.csv", "file-with-spaces.csv", "Spaces in filename"),
        ("restaurant/data.json", "restaurantdata.json", "Path characters"),
        ("🍕_pizza_place.txt", "_pizza_place.txt", "Emoji in filename"),
        ("file***name.txt", "filename.txt", "Special characters"),
        ("multiple---dashes.csv", "multiple-dashes.csv", "Multiple dashes"),
    ]
    
    for input_filename, expected, description in test_cases:
        result = sanitize_filename(input_filename)
        status = "✓" if result == expected else "✗"
        print(f"{status} {description}: '{input_filename}' → '{result}'")
        if result != expected:
            print(f"   Expected: '{expected}'")

def test_dataframe_unicode():
    """Test Unicode handling in DataFrames"""
    print("\nTesting DataFrame Unicode handling...")
    print("(Skipping DataFrame test - pandas not imported)")
    
    # Test individual Unicode strings as they would appear in data
    test_strings = [
        'Café Français',
        'Pizzería Italia', 
        '中華料理店',
        'Taco 🌮 Place',
        'Restaurant™ & Bar®'
    ]
    
    print("\nTesting individual restaurant names:")
    for test_str in test_strings:
        cleaned = clean_unicode_text(test_str)
        print(f"  '{test_str}' → '{cleaned}'")

if __name__ == "__main__":
    print("=== Unicode Handling Tests ===\n")
    test_unicode_cleaning()
    test_filename_sanitization()
    test_dataframe_unicode()
    print("\n=== Tests Complete ===")