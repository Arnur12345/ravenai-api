#!/usr/bin/env python3
"""
Comprehensive End-to-End Workflow Test for Vexa Platform

This script orchestrates a complete user workflow test, simulating a real-world scenario
from user registration to transcript processing by the RAG system.

Test Flow:
1. User Registration and API Key Generation via Admin API
2. Launch 10 concurrent transcription bots to the same meeting
3. Retrieve meeting transcript via API Gateway
4. Verify RAG system processing through direct database queries

Requirements:
- All services must be running via Docker Compose
- The test meeting URL must be accessible
- Required dependencies: httpx, qdrant-client, elasticsearch

Author: AI Assistant
Date: 2025
"""

import asyncio
import json
import logging
import os
import random
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

try:
    import httpx
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from elasticsearch import AsyncElasticsearch
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Please install required packages:")
    print("pip install httpx qdrant-client elasticsearch python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('e2e_test_results.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

class E2ETestConfig:
    """Configuration for E2E test execution"""
    
    def __init__(self):
        # Service URLs based on environment variables
        self.api_gateway_port = os.getenv('API_GATEWAY_HOST_PORT', '18056')
        self.admin_api_port = os.getenv('ADMIN_API_HOST_PORT', '18057')
        self.qdrant_port = os.getenv('QDRANT_HOST_PORT', '16333')
        self.elasticsearch_port = os.getenv('ELASTICSEARCH_HOST_PORT', '19200')
        
        self.api_gateway_url = f"http://localhost:{self.api_gateway_port}"
        self.admin_api_url = f"http://localhost:{self.admin_api_port}"
        self.qdrant_url = f"http://localhost:{self.qdrant_port}"
        self.elasticsearch_url = f"http://localhost:{self.elasticsearch_port}"
        
        # Test configuration
        self.admin_token = os.getenv('ADMIN_API_TOKEN', 'token')
        self.test_meeting_url = "https://meet.google.com/ttw-qdru-bfx"
        self.native_meeting_id = self.test_meeting_url.split("/")[-1]
        self.platform = "google_meet"
        self.concurrent_bots = 10
        self.poll_interval = 5  # seconds
        self.max_poll_attempts = 60  # 5 minutes total
        self.rag_processing_delay = 30  # seconds to wait for RAG processing

class E2ETestRunner:
    """Main class for running the end-to-end workflow test"""
    
    def __init__(self, config: E2ETestConfig):
        self.config = config
        self.test_user_email = f"e2e_test_{random.randint(100000, 999999)}@example.com"
        self.test_user_id: Optional[int] = None
        self.test_api_key: Optional[str] = None
        self.meeting_ids: List[str] = []
        self.transcript_data: Optional[Dict] = None
        
        # Test results tracking
        self.results = {
            'test_start_time': datetime.now(),
            'user_registration': False,
            'api_key_generation': False,
            'concurrent_bots_launched': 0,
            'transcript_retrieved': False,
            'rag_qdrant_verified': False,
            'rag_elasticsearch_verified': False,
            'total_success': False,
            'errors': []
        }
    
    async def run_complete_test(self) -> Dict[str, Any]:
        """
        Execute the complete end-to-end workflow test
        
        Returns:
            Dictionary containing test results and status
        """
        logger.info("=" * 80)
        logger.info("STARTING COMPREHENSIVE END-TO-END WORKFLOW TEST")
        logger.info("=" * 80)
        logger.info(f"Test Configuration:")
        logger.info(f"  API Gateway: {self.config.api_gateway_url}")
        logger.info(f"  Admin API: {self.config.admin_api_url}")
        logger.info(f"  Test Meeting: {self.config.test_meeting_url}")
        logger.info(f"  Concurrent Bots: {self.config.concurrent_bots}")
        logger.info(f"  Test User Email: {self.test_user_email}")
        
        try:
            # Step 1: User Registration and API Key Generation
            await self._step_1_user_registration()
            
            # Step 2: Launch Concurrent Bots
            await self._step_2_launch_concurrent_bots()
            
            # Step 3: Retrieve Transcript
            await self._step_3_retrieve_transcript()
            
            # Step 4: Verify RAG System
            await self._step_4_verify_rag_system()
            
            # Calculate final success
            self.results['total_success'] = (
                self.results['user_registration'] and
                self.results['api_key_generation'] and
                self.results['concurrent_bots_launched'] >= self.config.concurrent_bots and
                self.results['transcript_retrieved'] and
                (self.results['rag_qdrant_verified'] or self.results['rag_elasticsearch_verified'])
            )
            
        except Exception as e:
            logger.error(f"Critical test failure: {e}", exc_info=True)
            self.results['errors'].append(f"Critical failure: {str(e)}")
        
        finally:
            self.results['test_end_time'] = datetime.now()
            self.results['test_duration'] = (
                self.results['test_end_time'] - self.results['test_start_time']
            ).total_seconds()
            
            await self._generate_test_report()
        
        return self.results
    
    async def _step_1_user_registration(self):
        """Step 1: Register a new user and generate API key"""
        logger.info("\n" + "="*50)
        logger.info("STEP 1: USER REGISTRATION AND API KEY GENERATION")
        logger.info("="*50)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Register new user
                logger.info(f"Registering new user: {self.test_user_email}")
                
                user_data = {
                    "email": self.test_user_email,
                    "name": "E2E Test User",
                    "password": "test_password_123"
                }
                
                response = await client.post(
                    urljoin(self.config.admin_api_url, "/auth/register"),
                    headers={
                        "Content-Type": "application/json"
                    },
                    json=user_data
                )
                
                if response.status_code in [200, 201]:
                    registration_response = response.json()
                    # The /auth/register endpoint returns UserLoginResponse with user and token
                    user_info = registration_response['user']
                    token_info = registration_response['token']
                    
                    self.test_user_id = user_info['id']
                    self.test_api_key = token_info
                    
                    self.results['user_registration'] = True
                    self.results['api_key_generation'] = True
                    
                    logger.info(f"✅ User registered successfully with ID: {self.test_user_id}")
                    logger.info(f"✅ API key generated successfully: {self.test_api_key[:10]}...")
                else:
                    raise Exception(f"User registration failed: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(f"❌ Step 1 failed: {e}")
                self.results['errors'].append(f"Step 1 - User registration: {str(e)}")
                raise
    
    async def _step_2_launch_concurrent_bots(self):
        """Step 2: Launch concurrent transcription bots"""
        logger.info("\n" + "="*50)
        logger.info("STEP 2: LAUNCH CONCURRENT TRANSCRIPTION BOTS")
        logger.info("="*50)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Create bot request data
                bot_request = {
                    "platform": self.config.platform,
                    "native_meeting_id": self.config.native_meeting_id,
                    "bot_name": f"E2E-Test-Bot",
                    "language": "en",
                    "task": "transcribe"
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "X-API-Key": self.test_api_key
                }
                
                logger.info(f"Launching {self.config.concurrent_bots} concurrent bots to meeting: {self.config.test_meeting_url}")
                
                # Create concurrent tasks for bot requests
                tasks = []
                for i in range(self.config.concurrent_bots):
                    task = self._launch_single_bot(client, bot_request, headers, i+1)
                    tasks.append(task)
                
                # Execute all bot requests concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                successful_bots = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"❌ Bot {i+1} failed: {result}")
                        self.results['errors'].append(f"Bot {i+1} launch failed: {str(result)}")
                    else:
                        successful_bots += 1
                        if 'id' in result:
                            self.meeting_ids.append(str(result['id']))
                        logger.info(f"✅ Bot {i+1} launched successfully (Meeting ID: {result.get('id', 'unknown')})")
                
                self.results['concurrent_bots_launched'] = successful_bots
                logger.info(f"📊 Summary: {successful_bots}/{self.config.concurrent_bots} bots launched successfully")
                
                if successful_bots == 0:
                    raise Exception("No bots were launched successfully")
                    
            except Exception as e:
                logger.error(f"❌ Step 2 failed: {e}")
                self.results['errors'].append(f"Step 2 - Concurrent bots: {str(e)}")
                raise
    
    async def _launch_single_bot(self, client: httpx.AsyncClient, bot_request: Dict, headers: Dict, bot_number: int) -> Dict:
        """Launch a single bot and return the response"""
        try:
            response = await client.post(
                urljoin(self.config.api_gateway_url, "/bots"),
                headers=headers,
                json=bot_request
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            raise Exception(f"Bot {bot_number} launch failed: {str(e)}")
    
    async def _step_3_retrieve_transcript(self):
        """Step 3: Retrieve the meeting transcript"""
        logger.info("\n" + "="*50)
        logger.info("STEP 3: RETRIEVE MEETING TRANSCRIPT")
        logger.info("="*50)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "X-API-Key": self.test_api_key
                }
                
                transcript_url = urljoin(
                    self.config.api_gateway_url, 
                    f"/transcripts/{self.config.platform}/{self.config.native_meeting_id}"
                )
                
                logger.info(f"Polling for transcript at: {transcript_url}")
                logger.info(f"Max attempts: {self.config.max_poll_attempts} (interval: {self.config.poll_interval}s)")
                
                for attempt in range(1, self.config.max_poll_attempts + 1):
                    logger.info(f"📡 Polling attempt {attempt}/{self.config.max_poll_attempts}")
                    
                    response = await client.get(transcript_url, headers=headers)
                    
                    if response.status_code == 200:
                        transcript_data = response.json()
                        
                        # Check if we have meaningful transcript segments
                        segments = transcript_data.get('segments', [])
                        if segments and len(segments) > 0:
                            # Check for actual content
                            content_segments = [s for s in segments if s.get('text', '').strip()]
                            if content_segments:
                                self.transcript_data = transcript_data
                                self.results['transcript_retrieved'] = True
                                logger.info(f"✅ Transcript retrieved successfully!")
                                logger.info(f"📄 Total segments: {len(segments)}")
                                logger.info(f"📝 Content segments: {len(content_segments)}")
                                logger.info(f"🔤 Sample text: {content_segments[0].get('text', '')[:100]}...")
                                return
                            else:
                                logger.info(f"📄 Transcript found but no content yet ({len(segments)} empty segments)")
                        else:
                            logger.info(f"📄 Transcript found but no segments yet")
                    
                    elif response.status_code == 404:
                        logger.info(f"📄 Transcript not yet available (404)")
                    else:
                        logger.warning(f"⚠️ Unexpected response: {response.status_code} - {response.text[:200]}")
                    
                    if attempt < self.config.max_poll_attempts:
                        await asyncio.sleep(self.config.poll_interval)
                
                # If we get here, polling timed out
                raise Exception(f"Transcript retrieval timed out after {self.config.max_poll_attempts} attempts")
                
            except Exception as e:
                logger.error(f"❌ Step 3 failed: {e}")
                self.results['errors'].append(f"Step 3 - Transcript retrieval: {str(e)}")
                raise
    
    async def _step_4_verify_rag_system(self):
        """Step 4: Verify RAG system processing"""
        logger.info("\n" + "="*50)
        logger.info("STEP 4: VERIFY RAG SYSTEM PROCESSING")
        logger.info("="*50)
        
        if not self.transcript_data:
            raise Exception("No transcript data available for RAG verification")
        
        # Wait for RAG processing
        logger.info(f"⏳ Waiting {self.config.rag_processing_delay} seconds for RAG system to process transcript...")
        await asyncio.sleep(self.config.rag_processing_delay)
        
        # Extract search terms from transcript
        search_terms = self._extract_search_terms()
        logger.info(f"🔍 Search terms for verification: {search_terms}")
        
        # Verify Qdrant
        await self._verify_qdrant(search_terms)
        
        # Verify Elasticsearch
        await self._verify_elasticsearch(search_terms)
        
        # Summary
        rag_success = self.results['rag_qdrant_verified'] or self.results['rag_elasticsearch_verified']
        if rag_success:
            logger.info("✅ RAG system verification successful!")
        else:
            logger.error("❌ RAG system verification failed!")
    
    def _extract_search_terms(self) -> List[str]:
        """Extract search terms from the transcript for verification"""
        if not self.transcript_data or not self.transcript_data.get('segments'):
            return ["meeting", "transcript", "test"]  # fallback terms
        
        # Combine all transcript text
        all_text = " ".join([
            segment.get('text', '') 
            for segment in self.transcript_data['segments'] 
            if segment.get('text', '').strip()
        ])
        
        if not all_text.strip():
            return ["meeting", "transcript", "test"]  # fallback terms
        
        # Extract meaningful words (simple approach)
        words = all_text.lower().split()
        # Filter out common words and keep meaningful terms
        meaningful_words = [
            word for word in words 
            if len(word) > 3 and word not in ['this', 'that', 'with', 'from', 'they', 'were', 'been', 'have']
        ]
        
        # Return first few unique meaningful words, or fallback
        unique_words = list(dict.fromkeys(meaningful_words))[:5]
        return unique_words if unique_words else ["meeting", "transcript"]
    
    async def _verify_qdrant(self, search_terms: List[str]):
        """Verify content exists in Qdrant vector database"""
        try:
            logger.info("🔍 Verifying Qdrant vector database...")
            
            # Get meeting ID for search
            meeting_id = None
            if self.meeting_ids:
                meeting_id = self.meeting_ids[0]
            elif self.transcript_data:
                meeting_id = str(self.transcript_data.get('id', ''))
            
            if not meeting_id:
                logger.warning("⚠️ No meeting ID available for Qdrant verification")
                return
            
            # Connect to Qdrant
            client = QdrantClient(url=self.config.qdrant_url)
            
            # Check if collection exists
            collections = client.get_collections()
            collection_name = "transcripts"  # Default collection name based on RAG implementation
            
            collection_exists = any(col.name == collection_name for col in collections.collections)
            
            if not collection_exists:
                logger.warning(f"⚠️ Qdrant collection '{collection_name}' not found")
                # Try to find any collections with points
                for col in collections.collections:
                    try:
                        info = client.get_collection(col.name)
                        if info.points_count > 0:
                            logger.info(f"🔍 Found collection '{col.name}' with {info.points_count} points")
                            collection_name = col.name
                            break
                    except:
                        continue
                else:
                    logger.warning("⚠️ No Qdrant collections with points found")
                    return
            
            # Perform search for each term
            found_results = False
            for term in search_terms[:3]:  # Limit to first 3 terms
                try:
                    # Search with the term (simplified approach)
                    # Note: This is a basic search - the actual RAG system might use embeddings
                    logger.info(f"🔍 Searching Qdrant for term: '{term}'")
                    
                    # Try to search with simple query (this might need adjustment based on actual implementation)
                    results = client.search(
                        collection_name=collection_name,
                        query_vector=[0.1] * 384,  # Dummy vector for basic search
                        limit=10,
                        query_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="content_id",
                                    match=models.MatchValue(value=meeting_id)
                                )
                            ]
                        ) if meeting_id else None
                    )
                    
                    if results:
                        found_results = True
                        logger.info(f"✅ Found {len(results)} results in Qdrant for term '{term}'")
                        # Log sample result
                        if results[0].payload:
                            sample_text = str(results[0].payload).get('content', '')[:100]
                            logger.info(f"📄 Sample content: {sample_text}...")
                        break
                        
                except Exception as e:
                    logger.debug(f"Qdrant search for '{term}' failed: {e}")
                    continue
            
            if found_results:
                self.results['rag_qdrant_verified'] = True
                logger.info("✅ Qdrant verification successful!")
            else:
                logger.warning("⚠️ No relevant content found in Qdrant")
                
        except Exception as e:
            logger.error(f"❌ Qdrant verification failed: {e}")
            self.results['errors'].append(f"Qdrant verification: {str(e)}")
    
    async def _verify_elasticsearch(self, search_terms: List[str]):
        """Verify content exists in Elasticsearch"""
        try:
            logger.info("🔍 Verifying Elasticsearch...")
            
            # Get meeting ID for search
            meeting_id = None
            if self.meeting_ids:
                meeting_id = self.meeting_ids[0]
            elif self.transcript_data:
                meeting_id = str(self.transcript_data.get('id', ''))
            
            # Connect to Elasticsearch
            es = AsyncElasticsearch(
                [self.config.elasticsearch_url],
                verify_certs=False,
                ssl_show_warn=False
            )
            
            try:
                # Check if Elasticsearch is available
                if not await es.ping():
                    logger.warning("⚠️ Elasticsearch is not responding")
                    return
                
                # Get all indices
                indices = await es.indices.get_alias(index="*")
                index_name = "transcripts"  # Default index name
                
                # Look for transcript-related index
                if index_name not in indices:
                    # Try to find any index with documents
                    for idx_name in indices.keys():
                        if not idx_name.startswith('.'):  # Skip system indices
                            try:
                                count = await es.count(index=idx_name)
                                if count['count'] > 0:
                                    logger.info(f"🔍 Found index '{idx_name}' with {count['count']} documents")
                                    index_name = idx_name
                                    break
                            except:
                                continue
                    else:
                        logger.warning("⚠️ No Elasticsearch indices with documents found")
                        return
                
                # Perform search for each term
                found_results = False
                for term in search_terms[:3]:  # Limit to first 3 terms
                    try:
                        logger.info(f"🔍 Searching Elasticsearch for term: '{term}'")
                        
                        query = {
                            "query": {
                                "bool": {
                                    "must": [
                                        {"match": {"content": term}}
                                    ]
                                }
                            }
                        }
                        
                        # Add meeting ID filter if available
                        if meeting_id:
                            query["query"]["bool"]["filter"] = [
                                {"term": {"content_id": meeting_id}}
                            ]
                        
                        results = await es.search(
                            index=index_name,
                            body=query,
                            size=10
                        )
                        
                        hits = results.get('hits', {}).get('hits', [])
                        if hits:
                            found_results = True
                            logger.info(f"✅ Found {len(hits)} results in Elasticsearch for term '{term}'")
                            # Log sample result
                            sample_content = hits[0].get('_source', {}).get('content', '')[:100]
                            logger.info(f"📄 Sample content: {sample_content}...")
                            break
                            
                    except Exception as e:
                        logger.debug(f"Elasticsearch search for '{term}' failed: {e}")
                        continue
                
                if found_results:
                    self.results['rag_elasticsearch_verified'] = True
                    logger.info("✅ Elasticsearch verification successful!")
                else:
                    logger.warning("⚠️ No relevant content found in Elasticsearch")
                    
            finally:
                await es.close()
                
        except Exception as e:
            logger.error(f"❌ Elasticsearch verification failed: {e}")
            self.results['errors'].append(f"Elasticsearch verification: {str(e)}")
    
    async def _generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("\n" + "="*80)
        logger.info("COMPREHENSIVE END-TO-END TEST REPORT")
        logger.info("="*80)
        
        # Test Summary
        logger.info(f"🕐 Test Duration: {self.results['test_duration']:.2f} seconds")
        logger.info(f"👤 Test User: {self.test_user_email}")
        logger.info(f"🔗 Test Meeting: {self.config.test_meeting_url}")
        
        # Step Results
        logger.info("\n📋 STEP RESULTS:")
        logger.info(f"  ✅ User Registration: {'PASS' if self.results['user_registration'] else '❌ FAIL'}")
        logger.info(f"  ✅ API Key Generation: {'PASS' if self.results['api_key_generation'] else '❌ FAIL'}")
        logger.info(f"  ✅ Concurrent Bots: {self.results['concurrent_bots_launched']}/{self.config.concurrent_bots} launched")
        logger.info(f"  ✅ Transcript Retrieval: {'PASS' if self.results['transcript_retrieved'] else '❌ FAIL'}")
        logger.info(f"  ✅ RAG Qdrant Verification: {'PASS' if self.results['rag_qdrant_verified'] else '❌ FAIL'}")
        logger.info(f"  ✅ RAG Elasticsearch Verification: {'PASS' if self.results['rag_elasticsearch_verified'] else '❌ FAIL'}")
        
        # Overall Result
        if self.results['total_success']:
            logger.info(f"\n🎉 OVERALL RESULT: ✅ SUCCESS!")
            logger.info("All critical test components passed successfully.")
        else:
            logger.error(f"\n💥 OVERALL RESULT: ❌ FAILURE!")
            logger.error("One or more critical test components failed.")
        
        # Error Summary
        if self.results['errors']:
            logger.info(f"\n⚠️ ERRORS ENCOUNTERED ({len(self.results['errors'])}):")
            for i, error in enumerate(self.results['errors'], 1):
                logger.error(f"  {i}. {error}")
        
        # Acceptance Criteria Check
        logger.info("\n📝 ACCEPTANCE CRITERIA VERIFICATION:")
        criteria = [
            ("Script executes without critical errors", not any("Critical" in error for error in self.results['errors'])),
            ("User registration and API key generation successful", self.results['user_registration'] and self.results['api_key_generation']),
            ("10 concurrent bot requests sent successfully", self.results['concurrent_bots_launched'] >= self.config.concurrent_bots),
            ("Meeting transcript successfully retrieved", self.results['transcript_retrieved']),
            ("Content found in RAG system databases", self.results['rag_qdrant_verified'] or self.results['rag_elasticsearch_verified'])
        ]
        
        all_criteria_met = True
        for criterion, met in criteria:
            status = "✅ PASS" if met else "❌ FAIL"
            logger.info(f"  {status}: {criterion}")
            if not met:
                all_criteria_met = False
        
        logger.info(f"\n🏆 ACCEPTANCE CRITERIA: {'✅ ALL MET' if all_criteria_met else '❌ NOT MET'}")
        
        # Save detailed results to file
        results_file = 'e2e_test_detailed_results.json'
        try:
            with open(results_file, 'w') as f:
                # Convert datetime objects to strings for JSON serialization
                serializable_results = self.results.copy()
                serializable_results['test_start_time'] = self.results['test_start_time'].isoformat()
                serializable_results['test_end_time'] = self.results['test_end_time'].isoformat()
                json.dump(serializable_results, f, indent=2)
            logger.info(f"📄 Detailed results saved to: {results_file}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save detailed results: {e}")

async def main():
    """Main function to run the E2E test"""
    print("🚀 Vexa Platform - Comprehensive End-to-End Workflow Test")
    print("=" * 80)
    
    # Initialize configuration
    config = E2ETestConfig()
    
    # Check if services are likely running by checking environment
    if not os.getenv('ADMIN_API_TOKEN'):
        print("⚠️ WARNING: ADMIN_API_TOKEN not found in environment.")
        print("Make sure Docker Compose services are running and .env file is configured.")
        print("Run: make up")
        
    # Initialize and run test
    test_runner = E2ETestRunner(config)
    results = await test_runner.run_complete_test()
    
    # Exit with appropriate code
    exit_code = 0 if results['total_success'] else 1
    print(f"\n🏁 Test completed with exit code: {exit_code}")
    
    return exit_code

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        sys.exit(1) 