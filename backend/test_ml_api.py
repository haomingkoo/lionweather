#!/usr/bin/env python3
"""
Test script to verify ML API endpoints and seed initial data if needed.
"""

import requests
import json
from datetime import datetime, timedelta
import random

BASE_URL = "http://localhost:8000"

def test_endpoint(name, url, expected_status=200):
    """Test an API endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == expected_status:
            print("✅ SUCCESS")
            data = response.json()
            print(f"Response preview: {json.dumps(data, indent=2)[:500]}...")
            return True
        else:
            print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def seed_test_data():
    """Seed some test weather data"""
    print(f"\n{'='*60}")
    print("Seeding test data...")
    print(f"{'='*60}")
    
    from app.services.data_store import DataStore, WeatherRecord
    
    data_store = DataStore()
    
    # Create 30 days of hourly data
    now = datetime.now()
    records_created = 0
    
    for days_ago in range(30):
        for hour in range(24):
            timestamp = now - timedelta(days=days_ago, hours=hour)
            
            # Generate realistic Singapore weather data
            base_temp = 28.0
            temp_variation = random.uniform(-3, 3)
            
            record = WeatherRecord(
                timestamp=timestamp,
                country="Singapore",
                location="Central",
                latitude=1.3521,
                longitude=103.8198,
                temperature=base_temp + temp_variation,
                rainfall=random.uniform(0, 10) if random.random() > 0.7 else 0,
                humidity=random.uniform(60, 90),
                wind_speed=random.uniform(5, 20),
                wind_direction=random.uniform(0, 360),
                pressure=random.uniform(1010, 1020),
                source_api="test_seed"
            )
            
            try:
                data_store.save_weather_record(record)
                records_created += 1
            except Exception as e:
                print(f"Error saving record: {e}")
                break
    
    print(f"✅ Created {records_created} test weather records")
    return records_created > 0


def main():
    print("\n" + "="*60)
    print("ML API Test Suite")
    print("="*60)
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Backend is not responding correctly")
            return
        print("✅ Backend is running")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("Make sure the backend is running on http://localhost:8000")
        return
    
    # Test ML endpoints
    tests = [
        ("24h Predictions", f"{BASE_URL}/api/ml/predictions/24h?country=Singapore", 404),  # Expect 404 if no data
        ("7d Predictions", f"{BASE_URL}/api/ml/predictions/7d?country=Singapore", 404),
        ("Current Weather", f"{BASE_URL}/api/ml/predictions/current?country=Singapore", 404),
        ("Accuracy Metrics", f"{BASE_URL}/api/ml/metrics/accuracy?parameter=temperature", 200),
        ("Model Comparison", f"{BASE_URL}/api/ml/metrics/comparison?parameter=temperature", 200),
        ("Radar Frames", f"{BASE_URL}/api/radar/frames?count=6", 200),
        ("Rainfall Data", f"{BASE_URL}/api/rainfall", 200),
    ]
    
    results = []
    for name, url, expected in tests:
        result = test_endpoint(name, url, expected)
        results.append((name, result))
    
    # Check if we need to seed data
    print(f"\n{'='*60}")
    print("Checking if data seeding is needed...")
    print(f"{'='*60}")
    
    response = requests.get(f"{BASE_URL}/api/ml/predictions/current?country=Singapore")
    if response.status_code == 404:
        print("⚠️  No weather data found. Would you like to seed test data?")
        print("This will create 30 days of hourly weather data for testing.")
        
        user_input = input("Seed test data? (y/n): ").strip().lower()
        if user_input == 'y':
            if seed_test_data():
                print("\n✅ Test data seeded successfully!")
                print("You can now test the ML endpoints again.")
                print("Run: python test_ml_api.py")
            else:
                print("\n❌ Failed to seed test data")
    else:
        print("✅ Weather data exists")
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
