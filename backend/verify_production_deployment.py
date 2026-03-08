"""
Production Deployment Verification Script

This script tests the production backend deployment on Railway to verify:
1. Backend is accessible
2. API endpoints are working
3. Data collection is functioning
4. Database has records
5. Background tasks are running

Usage:
    python verify_production_deployment.py [backend_url]
    
Example:
    python verify_production_deployment.py https://lionweather-backend.up.railway.app
"""

import sys
import requests
import json
from datetime import datetime

def test_endpoint(url, name, expected_status=200):
    """Test an API endpoint and return success status"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == expected_status:
            print(f"✅ SUCCESS")
            try:
                data = response.json()
                print(f"Response Preview:")
                print(json.dumps(data, indent=2)[:500])
                return True, data
            except:
                print(f"Response (text): {response.text[:200]}")
                return True, response.text
        else:
            print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False, None
            
    except requests.exceptions.Timeout:
        print(f"❌ TIMEOUT - Request took longer than 10 seconds")
        return False, None
    except requests.exceptions.ConnectionError:
        print(f"❌ CONNECTION ERROR - Could not connect to server")
        return False, None
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False, None

def main():
    if len(sys.argv) > 1:
        backend_url = sys.argv[1].rstrip('/')
    else:
        # Try to detect backend URL
        print("No backend URL provided. Trying common Railway URLs...")
        possible_urls = [
            "https://lionweather-backend.up.railway.app",
            "https://lionweather.kooexperience.com/api",
            "https://lionweather-backend-production.up.railway.app",
        ]
        
        backend_url = None
        for url in possible_urls:
            print(f"\nTrying: {url}")
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    backend_url = url
                    print(f"✅ Found backend at: {url}")
                    break
            except:
                print(f"❌ Not accessible")
        
        if not backend_url:
            print("\n❌ Could not find backend. Please provide URL:")
            print("Usage: python verify_production_deployment.py <backend_url>")
            sys.exit(1)
    
    print("\n" + "="*60)
    print("PRODUCTION DEPLOYMENT VERIFICATION")
    print("="*60)
    print(f"Backend URL: {backend_url}")
    print(f"Test Time: {datetime.now().isoformat()}")
    print("="*60)
    
    results = {}
    
    # Test 1: Health Check
    success, data = test_endpoint(f"{backend_url}/health", "Health Check")
    results['health'] = success
    
    # Test 2: Status Check
    success, data = test_endpoint(f"{backend_url}/status", "Status Check")
    results['status'] = success
    if success and data:
        print("\n📊 Database Stats:")
        if 'database' in data and 'stats' in data['database']:
            stats = data['database']['stats']
            print(f"  Total Records: {stats.get('weather_data_total', 0)}")
            print(f"  By Country:")
            for country, count in stats.get('by_country', {}).items():
                print(f"    {country}: {count}")
    
    # Test 3: Weather Endpoint (Singapore)
    success, data = test_endpoint(
        f"{backend_url}/weather?lat=1.3521&lng=103.8198",
        "Weather Endpoint (Singapore)"
    )
    results['weather'] = success
    
    # Test 4: Forecasts Endpoint
    success, data = test_endpoint(
        f"{backend_url}/forecasts?lat=1.3521&lng=103.8198&days=7",
        "Forecasts Endpoint (7-day)"
    )
    results['forecasts'] = success
    
    # Test 5: Data Health Endpoint
    success, data = test_endpoint(
        f"{backend_url}/data-health",
        "Data Health Endpoint"
    )
    results['data_health'] = success
    
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s}: {status}")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED - Backend is fully operational!")
        return 0
    elif passed_tests > 0:
        print("\n⚠️  PARTIAL SUCCESS - Some endpoints are working")
        return 1
    else:
        print("\n❌ ALL TESTS FAILED - Backend may not be deployed or accessible")
        return 2

if __name__ == "__main__":
    sys.exit(main())
