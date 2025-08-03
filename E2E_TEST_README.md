# Comprehensive End-to-End Workflow Test

## Overview

This test script validates the complete Vexa platform workflow from user registration to transcript processing by the RAG system. It simulates a real-world scenario where multiple bots join a meeting, transcribe content, and verify that the data flows correctly through all system components.

## What This Test Does

### Step 1: User Registration & API Key Generation
- Creates a new test user via the public registration API (`/auth/register`)
- Automatically receives an API key in the registration response
- Validates authentication flow

### Step 2: Concurrent Bot Launching
- Launches 10 concurrent transcription bots to the same Google Meet
- Tests system's ability to handle concurrent requests
- Validates bot container creation and management

### Step 3: Transcript Retrieval
- Polls the transcript endpoint until content is available
- Validates that meaningful transcript data is captured
- Tests real-time data flow from bots to API

### Step 4: RAG System Verification
- Waits for RAG processing pipeline to complete
- Searches for transcript content in Qdrant (vector database)
- Searches for transcript content in Elasticsearch (text search)
- Confirms end-to-end data pipeline functionality

## Prerequisites

### 1. Environment Setup
```bash
# Ensure all services are running
make up

# Verify services are healthy
docker-compose ps
```

### 2. Install Test Dependencies
```bash
pip install -r test_requirements.txt
```

Required packages:
- `httpx>=0.27.0` - Async HTTP client
- `qdrant-client>=1.7.0` - Vector database client
- `elasticsearch>=8.11.0` - Text search client
- `python-dotenv>=1.0.0` - Environment management

### 3. Environment Configuration
Ensure your `.env` file contains:
```env
ADMIN_API_TOKEN=token
API_GATEWAY_HOST_PORT=18056
ADMIN_API_HOST_PORT=18057
QDRANT_HOST_PORT=16333
ELASTICSEARCH_HOST_PORT=19200
```

## Running the Test

### Basic Execution
```bash
python test_e2e_workflow.py
```

### Expected Output
The test will provide real-time feedback:
```
🚀 Vexa Platform - Comprehensive End-to-End Workflow Test
================================================================================
STEP 1: USER REGISTRATION AND API KEY GENERATION
==================================================
✅ User registered successfully with ID: 123
✅ API key received in registration response: ByWb1qps...

STEP 2: LAUNCH CONCURRENT TRANSCRIPTION BOTS
===============================================
✅ Bot 1 launched successfully (Meeting ID: 456)
✅ Bot 2 launched successfully (Meeting ID: 457)
...
📊 Summary: 10/10 bots launched successfully

STEP 3: RETRIEVE MEETING TRANSCRIPT
====================================
📡 Polling attempt 1/60
📄 Transcript found but no content yet
...
✅ Transcript retrieved successfully!
📄 Total segments: 25
📝 Content segments: 18

STEP 4: VERIFY RAG SYSTEM PROCESSING
====================================
🔍 Verifying Qdrant vector database...
✅ Found 3 results in Qdrant for term 'meeting'
✅ Qdrant verification successful!

🔍 Verifying Elasticsearch...
✅ Found 5 results in Elasticsearch for term 'transcript'
✅ Elasticsearch verification successful!
```

## Test Results

### Console Output
Real-time progress and results are displayed in the console with clear status indicators.

### Log Files
- `e2e_test_results.log` - Detailed execution log
- `e2e_test_detailed_results.json` - Machine-readable test results

### Exit Codes
- `0` - All tests passed successfully
- `1` - One or more tests failed
- `130` - Test interrupted by user (Ctrl+C)

## Acceptance Criteria Verification

The test automatically verifies all required acceptance criteria:

✅ **Script executes without errors**
✅ **User registration and API key generation successful**
✅ **10 concurrent bot requests sent successfully**
✅ **Meeting transcript successfully retrieved**
✅ **Content found in RAG system databases**

## Configuration Options

### Test Meeting
Default: `https://meet.google.com/ttw-qdru-bfx`

To use a different meeting, modify the `test_meeting_url` in the script or extend it to accept command-line arguments.

### Concurrent Bots
Default: 10 bots

Modify `concurrent_bots` in `E2ETestConfig` class to test with different numbers.

### Polling Configuration
- **Max attempts**: 60 (5 minutes total)
- **Poll interval**: 5 seconds
- **RAG processing delay**: 30 seconds

### Timeouts
- **HTTP requests**: 30-60 seconds
- **Overall test**: No limit (depends on transcript availability)

## Troubleshooting

### Common Issues

**1. Services Not Running**
```
Error: Connection refused
Solution: Run `make up` to start all services
```

**2. Missing Dependencies**
```
Error: Missing required dependency
Solution: Run `pip install -r test_requirements.txt`
```

**3. Authentication Failure**
```
Error: Invalid admin token
Solution: Check ADMIN_API_TOKEN in .env file
```

**4. No Transcript Content**
```
Warning: Transcript found but no content yet
Solution: Wait longer or check if bots are actually in the meeting
```

**5. RAG Verification Failed**
```
Error: No content found in databases
Solution: Wait longer for processing or check RAG service logs
```

### Debug Mode
For additional debugging information, modify the logging level:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Service Health Checks
Verify individual services:
```bash
# API Gateway
curl http://localhost:18056/

# Admin API
curl http://localhost:18057/

# RAG System
curl http://localhost:18124/health

# Qdrant
curl http://localhost:16333/collections

# Elasticsearch
curl http://localhost:19200/_cluster/health
```

## Architecture Notes

### Async Design
The test uses modern Python async/await patterns for optimal performance:
- Concurrent bot launching with `asyncio.gather()`
- Async HTTP clients with connection pooling
- Non-blocking database operations

### Error Handling
Comprehensive error handling at each step:
- Individual bot failures don't stop the entire test
- Network timeouts are handled gracefully
- Database connection issues are logged but don't crash the test

### Scalability
The test is designed to scale:
- Configurable number of concurrent bots
- Adjustable timeouts and retry logic
- Extensible for additional verification steps

## Integration with CI/CD

This test can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run E2E Test
  run: |
    make up
    sleep 30  # Wait for services to be ready
    python test_e2e_workflow.py
  env:
    ADMIN_API_TOKEN: ${{ secrets.ADMIN_API_TOKEN }}
```

## Contributing

When modifying this test:
1. Maintain backward compatibility with the acceptance criteria
2. Add comprehensive logging for new features
3. Update this README with any configuration changes
4. Test with different meeting URLs and bot counts 