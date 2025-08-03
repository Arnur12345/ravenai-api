# Vexa API Gateway

The main entry point for the Vexa platform APIs, providing secure access to all platform services including bot management, transcription retrieval, and AI-powered meeting queries.

## Features

- **Bot Management**: Start/stop transcription bots for various meeting platforms
- **Transcription Retrieval**: Access meeting transcripts and metadata
- **AI-Powered Queries**: Ask questions about meeting content using RAG (Retrieval-Augmented Generation)
- **User Management**: Token-based authentication and user administration
- **Service Routing**: Secure forwarding to internal microservices

## Authentication

Two types of API keys are supported:

1. **`X-API-Key`**: Required for all regular client operations (managing bots, getting transcripts, querying meetings)
2. **`X-Admin-API-Key`**: Required only for administrative endpoints (prefixed with `/admin`)

Include the appropriate header in your requests:

```bash
curl -H "X-API-Key: your-api-key" ...
```

## API Endpoints

### Query Endpoints

#### POST /v1/query

Ask questions about meeting content using AI-powered search and generation.

**Request:**
```json
{
  "question": "What were the main topics discussed?",
  "meeting_id": "meeting-uuid",
  "k": 5
}
```

**Response:**
```json
{
  "answer": "The main topics discussed were...",
  "meeting_id": "meeting-uuid",
  "sources": [
    {
      "content": "Relevant transcript segment...",
      "timestamp": "2024-01-15T10:30:00Z",
      "speaker": "John Doe",
      "score": 0.95
    }
  ],
  "total_sources": 3
}
```

**Authentication:** Requires `X-API-Key`

**Authorization:** User must have access to the specified `meeting_id`

**Example:**
```bash
curl -X POST http://localhost:8000/v1/query \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What decisions were made?",
    "meeting_id": "your-meeting-id",
    "k": 5
  }'
```

### Bot Management

#### POST /bot/start
Start a transcription bot for a meeting.

#### POST /bot/stop
Stop a running transcription bot.

#### PUT /bot/config
Update bot configuration.

#### GET /bot/status
Get current bot status.

### Transcription Retrieval

#### GET /meetings
List user's meetings.

#### GET /transcripts/{platform}/{native_meeting_id}
Get transcript for a specific meeting.

#### PUT /meetings/{platform}/{native_meeting_id}
Update meeting metadata.

#### DELETE /meetings/{platform}/{native_meeting_id}
Delete a meeting.

### User Management

#### PUT /user/webhook
Set user webhook URL for notifications.

### Health Check

#### GET /health
Check API Gateway health status.

## Environment Variables

```bash
# Service URLs
ADMIN_API_URL=http://admin-api:8000
BOT_MANAGER_URL=http://bot-manager:8000
TRANSCRIPTION_COLLECTOR_URL=http://transcription-collector:8000
VEXA_RAG_URL=http://vexa-contextual-rag:8000

# Database
DATABASE_URL=postgresql://user:password@localhost/vexa

# CORS (optional)
CORS_ORIGINS=http://localhost:3000,https://app.vexa.com
```

## Development

### Running Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export DATABASE_URL="postgresql://user:password@localhost/vexa"
export ADMIN_API_URL="http://localhost:8001"
export BOT_MANAGER_URL="http://localhost:8002"
export TRANSCRIPTION_COLLECTOR_URL="http://localhost:8003"
export VEXA_RAG_URL="http://localhost:8004"
```

3. Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing

Run the test script to verify all endpoints:

```bash
# Set test environment variables
export API_GATEWAY_URL="http://localhost:8000"
export TEST_API_KEY="your-test-api-key"
export TEST_MEETING_ID="your-test-meeting-id"

# Run tests
python test_query_endpoint.py
```

### Docker

Build and run with Docker:

```bash
docker build -t vexa-api-gateway .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:password@db/vexa" \
  -e ADMIN_API_URL="http://admin-api:8000" \
  vexa-api-gateway
```

## Error Handling

The API Gateway returns standard HTTP status codes:

- **200**: Success
- **400**: Bad Request (invalid request format)
- **401**: Unauthorized (missing or invalid API key)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found (resource doesn't exist or access denied)
- **422**: Unprocessable Entity (validation errors)
- **503**: Service Unavailable (downstream service error)

Error responses include detailed messages:

```json
{
  "detail": "Meeting with ID abc123 not found or access denied"
}
```

## Security

- All endpoints require valid API keys
- Meeting access is restricted to authorized users
- Requests are validated using Pydantic models
- Sensitive data is not logged
- CORS is configurable for web applications

## Monitoring

- Health check endpoint: `GET /health`
- Automatic OpenAPI documentation: `GET /docs`
- Request/response logging for debugging
- Connection pooling for downstream services

## Architecture

The API Gateway acts as a reverse proxy and authentication layer:

```
Client → API Gateway → Internal Services
                    ├── Admin API
                    ├── Bot Manager
                    ├── Transcription Collector
                    └── Vexa RAG System
```

## Contributing

1. Follow existing code patterns and conventions
2. Add tests for new endpoints
3. Update documentation for API changes
4. Ensure proper error handling and logging
5. Test with all supported authentication methods

## Support

For issues or questions:
- Check the logs for detailed error messages
- Verify environment variables are set correctly
- Ensure all dependent services are running
- Test with the provided test script