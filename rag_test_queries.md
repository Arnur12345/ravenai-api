# RAG System Query Commands

## Available Meetings with Transcripts

Based on database analysis, these meetings have transcript content:

- **Meeting 44**: 169 transcript segments (most content)
- **Meeting 54**: 117 transcript segments  
- **Meeting 30**: 17 transcript segments
- **Meeting 32**: 3 transcript segments

## Working Query Commands

### Test with Meeting 44 (Most Content)

```bash
# PowerShell Command
$body = @{
    question = "What was discussed in this meeting?"
    meeting_id = "44"
    k = 5
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:18124/search" -Method POST -ContentType "application/json" -Body $body
```

### Test with Meeting 30 (Meaningful Content)

```bash
# PowerShell Command  
$body = @{
    question = "What tasks were discussed?"
    meeting_id = "30"
    k = 3
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:18124/search" -Method POST -ContentType "application/json" -Body $body
```

### Test with Meeting 32 (Short Content)

```bash
# PowerShell Command
$body = @{
    question = "What was said in this meeting?"
    meeting_id = "32"
    k = 2
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:18124/search" -Method POST -ContentType "application/json" -Body $body
```

## Note

The RAG system requires transcripts to be indexed in Qdrant/Elasticsearch. Currently, the indexing process is failing due to Voyage AI rate limits. To make these queries work, you need to:

1. Configure Voyage AI billing/payment method
2. Or switch to a different embedding model
3. Or manually index the transcripts using the `/index` endpoint

## Alternative: Direct Database Query

If RAG indexing is not working, you can query transcripts directly from the database:

```sql
-- Get all transcripts for a meeting
SELECT t.text, t.speaker, t.start_time, t.end_time 
FROM transcriptions t 
WHERE t.meeting_id = 44 
ORDER BY t.start_time;
``` 