# Vexa Contextual RAG – Query Guide

This guide explains **only** how to query Vexa’s Contextual RAG service to obtain answers grounded in meeting transcripts.  Everything here is distilled from the E2E workflow but stripped of user-creation, Docker, or bot-launching details.

---

## 1 . Service Endpoint

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `POST` | `/search` | Hybrid search (semantic + BM25) over indexed meeting transcripts and answer generation |

The service listens on port `8000` inside the container.  If you exposed it on host port **8124** (default in `docker-compose.yml`) the full URL is:

```text
http://localhost:8124/search
```

> Replace *8124* with your chosen host-side port if you mapped it differently.

---

## 2 . Request Schema

```jsonc
{
  "question": "string, required",      // the user’s natural-language question
  "meeting_id": "string, required",   // DB-level meeting identifier to constrain the search
  "k": 5                               // optional, number of chunks to retrieve (default 5)
}
```

* `meeting_id` must match the `id` column in the `meetings` table **or** the `content_id` embedded in Qdrant/Elasticsearch.  If you obtained the transcript via `/transcripts/{platform}/{native_meeting_id}`, the JSON payload contains `id` – use that value here.
* `k` controls how many high-scoring transcript chunks are returned and used as context for the language-model answer.

### Minimal example

```bash
curl -X POST http://localhost:8124/search \
     -H "Content-Type: application/json" \
     -d '{
           "question": "What were the project deadlines?", \
           "meeting_id": "42"                    # example ID
         }'
```

---

## 3 . Response Schema

```jsonc
{
  "answer": "string",                // LLM-generated answer grounded in the transcript
  "meeting_id": "string",           // echoes the meeting ID you supplied
  "sources": [                       // up to k contextual chunks
    {
      "content": "string",          // raw or contextualised sentence/paragraph
      "timestamp": "hh:mm:ss",      // when the chunk starts in the meeting
      "speaker": "string",          // speaker name if available
      "score": 0.873                 // hybrid relevance score (semantic+BM25)
    }
  ],
  "total_sources": 5                  // may be less than k if fewer chunks exist
}
```

Only fields listed above are guaranteed; the service may include extra keys in future versions.

---

## 4 . End-to-End Example

Assume you already have:

* Meeting transcript indexed under **meeting_id = 18** (the registration/login phase in the E2E script created this).

### Query

```bash
curl -s -X POST http://localhost:8124/search \
     -H "Content-Type: application/json" \
     -d '{
            "question": "Summarise the discussion about budget overruns.",
            "meeting_id": "18",
            "k": 8
         }' | jq
```

### Typical Response

```jsonc
{
  "answer": "The team acknowledged that the budget overran by 12%.  The primary drivers were accelerated hiring and unplanned vendor fees.  Mitigation steps include freezing new roles and renegotiating the vendor contract.",
  "meeting_id": "18",
  "sources": [
    {
      "content": "…we overspent by about twelve percent mainly because we brought in three extra contractors…",
      "timestamp": "00:23:14",
      "speaker": "CFO",
      "score": 0.92
    },
    {
      "content": "…going forward we plan to pause hiring and revisit the vendor agreement…",
      "timestamp": "00:24:03",
      "speaker": "Project Lead",
      "score": 0.88
    }
  ],
  "total_sources": 2
}
```

---

## 5 . Error Handling

| HTTP Code | Meaning | Typical Cause |
| --------- | ------- | ------------- |
| `400` | Validation error | Missing `question` or `meeting_id` |
| `404` | No content found | Meeting ID exists but no transcript chunks indexed yet |
| `503` | Search engines unavailable | Qdrant/Elasticsearch not initialised inside the RAG container |

---

## 6 . Tips & Tricks

1. **Meeting-specific filtering** – Always supply `meeting_id` to avoid cross-meeting leakage.
2. **Increase `k`** if you need more provenance chunks (max reasonable ~100).
3. **Speaker or timestamp filters** – not exposed via the HTTP API yet, but the underlying hybrid_search code supports extra filters; extending the API is straightforward.
4. **Performance** – First query after container restart is slower (~1–2 s) while search engines warm up.

---

*Document generated automatically from `test_e2e_workflow.py` and RAG source code.* 