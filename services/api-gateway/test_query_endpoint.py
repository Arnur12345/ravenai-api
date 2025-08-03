#!/usr/bin/env python3
"""
Test script for the new /v1/query endpoint in the API Gateway.

This script tests:
1. Authentication (valid/invalid API keys)
2. Authorization (access to meeting_id)
3. Request forwarding to RAG system
4. Response handling

Usage:
    python test_query_endpoint.py

Environment variables required:
    - API_GATEWAY_URL: URL of the API Gateway (default: http://localhost:8000)
    - TEST_API_KEY: Valid API key for testing
    - TEST_MEETING_ID: Meeting ID that the user has access to
"""

import asyncio
import os
import httpx
import json
from typing import Dict, Any

# Configuration
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")
TEST_API_KEY = os.getenv("TEST_API_KEY", "your-test-api-key-here")
TEST_MEETING_ID = os.getenv("TEST_MEETING_ID", "test-meeting-id")


async def test_query_endpoint():
    """Test the /v1/query endpoint with various scenarios."""
    
    async with httpx.AsyncClient() as client:
        print("🧪 Testing API Gateway /v1/query endpoint\n")
        
        # Test 1: Valid request
        print("📋 Test 1: Valid query request")
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/v1/query",
                headers={
                    "X-API-Key": TEST_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "question": "What were the main topics discussed in this meeting?",
                    "meeting_id": TEST_MEETING_ID,
                    "k": 5
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"   Answer: {result.get('answer', 'N/A')[:100]}...")
                print(f"   Sources: {result.get('total_sources', 0)} found")
                print("   ✅ Success")
            else:
                print(f"   Response: {response.text}")
                print("   ❌ Failed")
        except Exception as e:
            print(f"   Error: {e}")
            print("   ❌ Failed")
        
        print()
        
        # Test 2: Missing API key
        print("📋 Test 2: Missing API key (should return 401)")
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/v1/query",
                headers={"Content-Type": "application/json"},
                json={
                    "question": "Test question",
                    "meeting_id": TEST_MEETING_ID
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 401:
                print("   ✅ Correctly rejected unauthorized request")
            else:
                print(f"   Response: {response.text}")
                print("   ❌ Should have returned 401")
        except Exception as e:
            print(f"   Error: {e}")
            print("   ❌ Failed")
        
        print()
        
        # Test 3: Invalid API key
        print("📋 Test 3: Invalid API key (should return 403)")
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/v1/query",
                headers={
                    "X-API-Key": "invalid-api-key",
                    "Content-Type": "application/json"
                },
                json={
                    "question": "Test question",
                    "meeting_id": TEST_MEETING_ID
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 403:
                print("   ✅ Correctly rejected invalid API key")
            else:
                print(f"   Response: {response.text}")
                print("   ❌ Should have returned 403")
        except Exception as e:
            print(f"   Error: {e}")
            print("   ❌ Failed")
        
        print()
        
        # Test 4: Invalid meeting ID
        print("📋 Test 4: Invalid meeting ID (should return 404)")
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/v1/query",
                headers={
                    "X-API-Key": TEST_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "question": "Test question",
                    "meeting_id": "non-existent-meeting-id"
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 404:
                print("   ✅ Correctly rejected invalid meeting ID")
            else:
                print(f"   Response: {response.text}")
                print("   ❌ Should have returned 404")
        except Exception as e:
            print(f"   Error: {e}")
            print("   ❌ Failed")
        
        print()
        
        # Test 5: Invalid request body
        print("📋 Test 5: Invalid request body (should return 422)")
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/v1/query",
                headers={
                    "X-API-Key": TEST_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "invalid_field": "test"
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 422:
                print("   ✅ Correctly rejected invalid request body")
            else:
                print(f"   Response: {response.text}")
                print("   ❌ Should have returned 422")
        except Exception as e:
            print(f"   Error: {e}")
            print("   ❌ Failed")
        
        print()
        
        # Test 6: Health check
        print("📋 Test 6: API Gateway health check")
        try:
            response = await client.get(f"{API_GATEWAY_URL}/health")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ API Gateway is healthy")
            else:
                print(f"   Response: {response.text}")
                print("   ❌ Health check failed")
        except Exception as e:
            print(f"   Error: {e}")
            print("   ❌ Failed")


def print_usage():
    """Print usage instructions."""
    print("\n📖 Usage Instructions:")
    print("\n1. Set environment variables:")
    print(f"   export API_GATEWAY_URL={API_GATEWAY_URL}")
    print(f"   export TEST_API_KEY=your-actual-api-key")
    print(f"   export TEST_MEETING_ID=your-actual-meeting-id")
    print("\n2. Ensure the API Gateway and RAG system are running")
    print("\n3. Run the test:")
    print("   python test_query_endpoint.py")
    print("\n4. Example curl command for manual testing:")
    print(f"   curl -X POST {API_GATEWAY_URL}/v1/query \\")
    print("     -H 'X-API-Key: your-api-key' \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"question\": \"What was discussed?\", \"meeting_id\": \"your-meeting-id\"}'")


if __name__ == "__main__":
    print("🚀 API Gateway Query Endpoint Test")
    print("=" * 50)
    
    if TEST_API_KEY == "your-test-api-key-here":
        print("⚠️  Warning: Using default TEST_API_KEY. Please set a valid API key.")
    
    if TEST_MEETING_ID == "test-meeting-id":
        print("⚠️  Warning: Using default TEST_MEETING_ID. Please set a valid meeting ID.")
    
    try:
        asyncio.run(test_query_endpoint())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
    finally:
        print_usage()