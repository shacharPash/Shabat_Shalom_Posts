#!/usr/bin/env python3
"""
Test script to verify hdate integration works correctly
and compare with previous Hebcal API results.
"""

import datetime
from make_shabbat_posts import hdate_shabbat_for_week, CITIES

def test_hdate_integration():
    """Test the hdate integration for all cities."""
    print("Testing hdate integration for Shabbat time calculations...")
    print("=" * 60)
    
    # Test with a specific Friday
    test_friday = datetime.date(2025, 1, 24)  # Friday, January 24, 2025
    
    print(f"Testing for Friday: {test_friday.strftime('%B %d, %Y')}")
    print()
    
    for city in CITIES:
        print(f"City: {city['name']}")
        print(f"Coordinates: {city['lat']}, {city['lon']}")
        print(f"Candle offset: {city['candle_offset']} minutes")
        
        try:
            info = hdate_shabbat_for_week(
                city["lat"], 
                city["lon"], 
                test_friday, 
                city["candle_offset"]
            )
            
            print(f"Parsha: {info.get('parsha', 'N/A')}")
            print(f"Candle lighting: {info.get('candle', 'N/A')}")
            print(f"Havdalah: {info.get('havdalah', 'N/A')}")
            
        except Exception as e:
            print(f"ERROR: {e}")
        
        print("-" * 40)
    
    print("Test completed!")

if __name__ == "__main__":
    test_hdate_integration()
