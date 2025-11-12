#!/usr/bin/env python3
"""
Advanced MusicBrainz connection troubleshooting and fixes
"""

import time
import logging
import musicbrainzngs
import requests
from urllib.parse import quote

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def test_user_agent_variations():
    """Test different user agent configurations"""
    print("\n=== Testing Different User Agent Configurations ===")
    
    user_agents = [
        ("lidarr-album-import-script", "1.0", "rutty.stuart@gmail.com"),
        ("LidarrMusicImporter", "1.0", "rutty.stuart@gmail.com"),
        ("MusicBrainzTest", "1.0", "rutty.stuart@gmail.com"),
        ("python-musicbrainzngs-test", "1.0", "rutty.stuart@gmail.com")
    ]
    
    for app_name, version, contact in user_agents:
        print(f"\nTrying user agent: {app_name}/{version}")
        try:
            musicbrainzngs.set_useragent(app_name, version, contact)
            musicbrainzngs.set_rate_limit(limit_or_interval=1.5)
            
            result = musicbrainzngs.search_artists(artist="Beatles", limit=1)
            artists = result.get("artist-list", [])
            if artists:
                print(f"✅ SUCCESS with {app_name}: Found {artists[0].get('name')}")
                return True, (app_name, version, contact)
            else:
                print(f"⚠️  No results with {app_name}")
                
        except musicbrainzngs.NetworkError as e:
            if "403" in str(e):
                print(f"❌ 403 error with {app_name}")
            else:
                print(f"❌ Network error with {app_name}: {e}")
        except Exception as e:
            print(f"❌ Error with {app_name}: {e}")
            
        time.sleep(2)  # Wait between attempts
    
    return False, None

def test_direct_api_with_custom_headers():
    """Test direct API calls with enhanced headers"""
    print("\n=== Testing Direct API with Custom Headers ===")
    
    headers_sets = [
        {
            'User-Agent': 'lidarr-album-import-script/1.0 python-musicbrainzngs/0.7.1 (rutty.stuart@gmail.com)',
            'Accept': 'application/xml',
            'Accept-Charset': 'UTF-8'
        },
        {
            'User-Agent': 'LidarrMusicImporter/1.0 (rutty.stuart@gmail.com)',
            'Accept': 'application/xml',
        },
        {
            'User-Agent': 'Mozilla/5.0 (compatible; LidarrMusicImporter/1.0; +mailto:rutty.stuart@gmail.com)',
            'Accept': 'application/xml',
        }
    ]
    
    for i, headers in enumerate(headers_sets, 1):
        print(f"\nTrying header set {i}...")
        try:
            url = "https://musicbrainz.org/ws/2/artist"
            params = {'query': 'artist:Beatles', 'limit': 1}
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ SUCCESS with header set {i}")
                print(f"Response length: {len(response.content)} bytes")
                return True, headers
            elif response.status_code == 403:
                print(f"❌ Still getting 403 with header set {i}")
            else:
                print(f"⚠️  Unexpected status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error with header set {i}: {e}")
            
        time.sleep(2)  # Wait between attempts
    
    return False, None

def test_with_proxy_bypass():
    """Test if we can bypass potential VPN blocking"""
    print("\n=== Testing Proxy/VPN Bypass Methods ===")
    
    import socket
    original_timeout = socket.getdefaulttimeout()
    
    try:
        # Try with different timeout settings
        musicbrainzngs.set_useragent("lidarr-album-import-script", "1.0", "rutty.stuart@gmail.com")
        musicbrainzngs.set_rate_limit(limit_or_interval=2.0)
        
        # Set a longer timeout
        socket.setdefaulttimeout(60)  # 60 second timeout
        
        print("Attempting with extended timeout...")
        result = musicbrainzngs.search_artists(artist="Beatles", limit=1)
        
        artists = result.get("artist-list", [])
        if artists:
            print(f"✅ SUCCESS with extended timeout: {artists[0].get('name')}")
            return True
        else:
            print("⚠️  No results even with extended timeout")
            
    except Exception as e:
        print(f"❌ Extended timeout failed: {e}")
    finally:
        # Always restore original timeout
        socket.setdefaulttimeout(original_timeout)
    
    return False

def test_alternative_endpoints():
    """Test alternative MusicBrainz endpoints"""
    print("\n=== Testing Alternative Endpoints ===")
    
    # Sometimes the main endpoint is blocked but mirror endpoints work
    endpoints = [
        "https://musicbrainz.org/ws/2/",
        "https://mb.musicbrainz.org/ws/2/",
    ]
    
    for endpoint in endpoints:
        print(f"\nTrying endpoint: {endpoint}")
        try:
            url = f"{endpoint}artist"
            params = {'query': 'artist:Beatles', 'limit': 1}
            headers = {
                'User-Agent': 'lidarr-album-import-script/1.0 (rutty.stuart@gmail.com)',
                'Accept': 'application/xml'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ SUCCESS with endpoint: {endpoint}")
                return True, endpoint
            else:
                print(f"❌ Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error with {endpoint}: {e}")
            
        time.sleep(2)
    
    return False, None

def test_with_slower_rate_limiting():
    """Test with very conservative rate limiting"""
    print("\n=== Testing with Ultra-Conservative Rate Limiting ===")
    
    try:
        musicbrainzngs.set_useragent("lidarr-album-import-script", "1.0", "rutty.stuart@gmail.com")
        
        # Try with very slow rate limiting
        for delay in [3.0, 5.0, 10.0]:
            print(f"\nTrying with {delay} second delays...")
            musicbrainzngs.set_rate_limit(limit_or_interval=delay)
            
            try:
                result = musicbrainzngs.search_artists(artist="Beatles", limit=1)
                artists = result.get("artist-list", [])
                if artists:
                    print(f"✅ SUCCESS with {delay}s delay: {artists[0].get('name')}")
                    return True, delay
                else:
                    print(f"⚠️  No results with {delay}s delay")
            except Exception as e:
                if "403" in str(e):
                    print(f"❌ Still getting 403 with {delay}s delay")
                else:
                    print(f"❌ Error with {delay}s delay: {e}")
                    
            time.sleep(delay + 1)  # Extra wait between tests
    
    except Exception as e:
        print(f"❌ Rate limiting test failed: {e}")
    
    return False, None

def main():
    """Run comprehensive MusicBrainz troubleshooting"""
    print("=== MusicBrainz Connection Troubleshooting ===")
    print("Attempting to resolve 403 errors and establish working connection...")
    
    # Try different approaches in order of preference
    tests = [
        ("Conservative Rate Limiting", test_with_slower_rate_limiting),
        ("User Agent Variations", test_user_agent_variations),
        ("Direct API Custom Headers", test_direct_api_with_custom_headers),
        ("Alternative Endpoints", test_alternative_endpoints),
        ("Proxy Bypass", test_with_proxy_bypass),
    ]
    
    working_solution = None
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            result = test_func()
            if isinstance(result, tuple) and result[0]:
                working_solution = (test_name, result)
                print(f"\n🎉 FOUND WORKING SOLUTION: {test_name}")
                break
            elif result is True:
                working_solution = (test_name, True)
                print(f"\n🎉 FOUND WORKING SOLUTION: {test_name}")
                break
            else:
                print(f"\n❌ {test_name} failed")
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
    
    print(f"\n{'='*50}")
    print("FINAL RESULTS")
    print('='*50)
    
    if working_solution:
        print(f"✅ SUCCESS: {working_solution[0]} works!")
        print("\nNext steps:")
        print("1. Use the working configuration in your main script")
        print("2. Test with your actual CSV data")
        print("3. Monitor for any rate limiting issues")
    else:
        print("❌ All tests failed. This suggests:")
        print("   - Your VPN/IP is completely blocked by MusicBrainz")
        print("   - MusicBrainz service issues")
        print("   - Network configuration problems")
        print("\nRecommendations:")
        print("   - Try disconnecting from VPN temporarily")
        print("   - Check MusicBrainz status at https://musicbrainz.org/")
        print("   - Consider using a different network")

if __name__ == "__main__":
    main()