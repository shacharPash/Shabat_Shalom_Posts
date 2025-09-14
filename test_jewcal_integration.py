#!/usr/bin/env python3
"""
Test script to verify jewcal integration works correctly
for both Shabbat and Yom Tov calculations.
"""

import datetime
from make_shabbat_posts import jewcal_times_for_date, CITIES

def test_jewcal_integration():
    """Test the jewcal integration for all cities."""
    print("Testing jewcal integration for Shabbat and Yom Tov time calculations...")
    print("=" * 70)
    
    # Test with a regular Shabbat
    test_shabbat = datetime.date(2025, 1, 24)  # Friday, January 24, 2025
    print(f"Testing regular Shabbat: {test_shabbat.strftime('%B %d, %Y')}")
    print()
    
    for city in CITIES:
        print(f"City: {city['name']}")
        print(f"Coordinates: {city['lat']}, {city['lon']}")
        print(f"Candle offset: {city['candle_offset']} minutes")
        
        try:
            info = jewcal_times_for_date(
                city["lat"], 
                city["lon"], 
                test_shabbat, 
                city["candle_offset"]
            )
            
            print(f"Event type: {info.get('event_type', 'N/A')}")
            print(f"Event name: {info.get('event_name', 'N/A')}")
            print(f"Parsha: {info.get('parsha', 'N/A')}")
            print(f"Candle lighting: {info.get('candle', 'N/A')}")
            print(f"Havdalah: {info.get('havdalah', 'N/A')}")
            print(f"Action: {info.get('action', 'N/A')}")
            
        except Exception as e:
            print(f"ERROR: {e}")
        
        print("-" * 40)
        break  # Only test first city for brevity
    
    print("\n" + "=" * 70)
    
    # Test with Yom Tov (Erev Pesach)
    test_yomtov = datetime.date(2025, 4, 12)  # Erev Pesach 2025
    print(f"Testing Yom Tov: {test_yomtov.strftime('%B %d, %Y')} (Erev Pesach)")
    print()
    
    city = CITIES[0]  # Test with Jerusalem
    print(f"City: {city['name']}")
    print(f"Coordinates: {city['lat']}, {city['lon']}")
    print(f"Candle offset: {city['candle_offset']} minutes")
    
    try:
        info = jewcal_times_for_date(
            city["lat"], 
            city["lon"], 
            test_yomtov, 
            city["candle_offset"]
        )
        
        print(f"Event type: {info.get('event_type', 'N/A')}")
        print(f"Event name: {info.get('event_name', 'N/A')}")
        print(f"Parsha: {info.get('parsha', 'N/A')}")
        print(f"Candle lighting: {info.get('candle', 'N/A')}")
        print(f"Havdalah: {info.get('havdalah', 'N/A')}")
        print(f"Action: {info.get('action', 'N/A')}")
        
    except Exception as e:
        print(f"ERROR: {e}")
    
    print("-" * 40)
    print("Test completed!")

if __name__ == "__main__":
    test_jewcal_integration()
