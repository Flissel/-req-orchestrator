# Batch Validation Guide

This guide explains how to validate multiple requirements efficiently using the batch validation endpoints with optimized performance settings.

## Overview

The system supports validating multiple requirements in a single request with automatic iterative improvement until quality gates pass. The batch validation system includes:

- **Parallel criterion fixes**: Process multiple failing criteria simultaneously
- **Early exit optimization**: Skip unnecessary evaluations when gating criteria fail
- **Real-time change tracking**: SSE events showing requirement transformations
- **Tier-based quality gates**: Gating (80%), Priority (70%), Polish (60%)

## Endpoints

### Single Requirement Auto-Validation

```
POST /api/v1/validate/auto
```

**Request Body:**
```json
{
  "requirement_id": "REQ-001",
  "requirement_text": "The system must authenticate users",
  "threshold": 0.8,
  "max_iterations": 5
}
```

**Response:**
```json
{
  "requirement_id": "REQ-001",
  "original_text": "The system must authenticate users",
  "final_text": "As a user, I want to authenticate with username and password...",
  "final_score": 0.85,
  "verdict": "release_ok",
  "iterations": [
    {
      "iteration_num": 1,
      "text_before": "The system must authenticate users",
      "text_after": "As a user, I want to authenticate...",
      "scores": {
        "atomic": 1.0,
        "clarity": 0.8,
        "testability": 0.9,
        ...
      },
      "score": 0.85,
      "fixes_applied": [
        {
          "criterion": "clarity",
          "old_text": "The system must authenticate users",
          "new_text": "As a user, I want to authenticate...",
          "score_before": 0.6,
          "score_after": 0.8
        }
      ]
    }
  ]
}
```

### Batch Auto-Validation

```
POST /api/v1/validate/auto/batch
```

**Request Body:**
```json
{
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "requirement_text": "The system must work"
    },
    {
      "requirement_id": "REQ-002",
      "requirement_text": "Users need login"
    },
    {
      "requirement_id": "REQ-003",
      "requirement_text": "Fast performance"
    }
  ],
  "threshold": 0.8,
  "max_iterations": 5
}
```

**Response:**
```json
{
  "results": [
    {
      "requirement_id": "REQ-001",
      "original_text": "The system must work",
      "final_text": "As a user, I want...",
      "final_score": 0.85,
      "verdict": "release_ok",
      "iterations": [...]
    },
    ...
  ]
}
```

## Performance Configuration

### .env Settings

```bash
# Parallel criterion fixes (recommended: 3)
# 1 = sequential (slowest, safest)
# 3 = parallel batches of 3 (2-3x faster)
# 9 = all parallel (fastest, higher API usage)
FIX_BATCH_SIZE=3

# Early exit optimization (recommended: true)
# false = always evaluate all criteria
# true = stop early on gating failure (40-50% faster)
EARLY_EXIT_ON_GATING=true
```

### Performance Impact

| Configuration | Speed | API Calls | Best For |
|---------------|-------|-----------|----------|
| `FIX_BATCH_SIZE=1` | Baseline | Low | Rate-limited APIs |
| `FIX_BATCH_SIZE=3` | 2-3x faster | Medium | Recommended default |
| `FIX_BATCH_SIZE=9` | 3-4x faster | High | High-throughput |
| `EARLY_EXIT_ON_GATING=true` | +40-50% | -40-50% | Skip failing reqs |

## Real-Time Change Tracking

The validation system emits Server-Sent Events (SSE) for real-time progress tracking:

### SSE Event: `requirement_updated`

```json
{
  "requirement_id": "REQ-001",
  "criterion": "clarity",
  "old_text": "The system must authenticate users",
  "new_text": "As a user, I want to authenticate with username and password",
  "score_before": 0.6,
  "score_after": 0.8
}
```

### SSE Event: `iteration_complete`

```json
{
  "requirement_id": "REQ-001",
  "iteration_num": 1,
  "score": 0.85,
  "verdict": "release_ok"
}
```

### SSE Event: `requirement_split`

```json
{
  "requirement_id": "REQ-001",
  "reason": "atomic_failure",
  "children_count": 3,
  "children_ids": ["REQ-001-001", "REQ-001-002", "REQ-001-003"]
}
```

## Usage Examples

### Example 1: Validate 20 Requirements

```bash
curl -X POST http://localhost:8087/api/v1/validate/auto/batch \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": [
      {"requirement_id": "REQ-001", "requirement_text": "System must work"},
      {"requirement_id": "REQ-002", "requirement_text": "Fast performance"},
      ...
      {"requirement_id": "REQ-020", "requirement_text": "Secure data"}
    ],
    "threshold": 0.8,
    "max_iterations": 5
  }'
```

### Example 2: With Custom Threshold

```bash
curl -X POST http://localhost:8087/api/v1/validate/auto/batch \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": [
      {"requirement_id": "REQ-001", "requirement_text": "System must authenticate"}
    ],
    "threshold": 0.7,
    "max_iterations": 3
  }'
```

### Example 3: Python Client

```python
import requests

requirements = [
    {"requirement_id": f"REQ-{i:03d}", "requirement_text": req_text}
    for i, req_text in enumerate([
        "System must authenticate users",
        "Fast response time required",
        "Data must be encrypted",
        # ... up to 20+ requirements
    ], start=1)
]

response = requests.post(
    "http://localhost:8087/api/v1/validate/auto/batch",
    json={
        "requirements": requirements,
        "threshold": 0.8,
        "max_iterations": 5
    }
)

results = response.json()["results"]
for result in results:
    print(f"{result['requirement_id']}: {result['verdict']} (score: {result['final_score']:.2f})")
```

### Example 4: Frontend Integration with SSE

```javascript
const eventSource = new EventSource('/api/v1/validate/auto/batch/stream');

eventSource.addEventListener('requirement_updated', (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.criterion} fixed: ${data.old_text.slice(0, 30)}... → ${data.new_text.slice(0, 30)}...`);
});

eventSource.addEventListener('iteration_complete', (event) => {
  const data = JSON.parse(event.data);
  console.log(`Iteration ${data.iteration_num} complete: ${data.verdict} (${data.score})`);
});

// Make batch validation request
fetch('/api/v1/validate/auto/batch', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    requirements: [/* ... */],
    threshold: 0.8,
    max_iterations: 5
  })
});
```

## Quality Tiers

### Gating Tier (80% threshold)
**Must ALL pass** for release approval:
- `atomic`: Single, indivisible capability
- `clarity`: Clear actor, action, and object
- `testability`: Verifiable with concrete test cases

### Priority Tier (70% threshold)
**Important but not blocking**:
- `design_independent`: No implementation details
- `unambiguous`: Single interpretation

### Polish Tier (60% threshold)
**Nice to have**:
- `concise`: Brief and to the point
- `consistent_language`: Standard terminology
- `measurability`: Quantifiable success criteria
- `purpose_independent`: No "why" or rationale

## Weighted Scoring

Final score calculation:
- **Gating criteria**: 50% weight
- **Priority criteria**: 30% weight
- **Polish criteria**: 20% weight

**Example:**
```
Gating avg:   0.9  × 50% = 0.45
Priority avg: 0.8  × 30% = 0.24
Polish avg:   0.7  × 20% = 0.14
─────────────────────────────
Final score:              0.83
```

## Iterative Improvement

Each requirement goes through up to `max_iterations` (default: 5) cycles:

1. **Evaluation**: Score all 10 criteria
2. **Gate check**: If gating criteria fail → apply fixes
3. **Priority check**: If priority criteria fail → apply fixes
4. **Polish check**: If polish criteria fail → apply fixes
5. **Verdict**:
   - `release_ok`: Final score ≥ threshold AND all gating pass
   - `needs_improvement`: Failed to reach threshold after max iterations
   - `split`: Atomic criterion failed, requirement split into children

## Advanced: Atomic Splitting

When the `atomic` criterion fails (score < 0.8), the requirement is automatically split into atomic sub-requirements:

**Before:**
```
REQ-001: "The system must authenticate users and log their activity"
```

**After Split:**
```
REQ-001-001: "As a user, I want to authenticate with username and password"
REQ-001-002: "As a user, I want my login activity to be logged"
```

The split creates child requirements that each satisfy a single capability.

## Troubleshooting

### Issue: Slow Batch Validation

**Solution:**
1. Increase `FIX_BATCH_SIZE` to 3 or higher
2. Enable `EARLY_EXIT_ON_GATING=true`
3. Reduce `max_iterations` for faster (but less refined) results

### Issue: High API Costs

**Solution:**
1. Lower `FIX_BATCH_SIZE` to 1
2. Disable `EARLY_EXIT_ON_GATING` to ensure quality
3. Use `MOCK_MODE=true` for testing (heuristic evaluation)

### Issue: Requirements Not Improving

**Possible causes:**
- Requirement is fundamentally flawed (consider manual rewrite)
- LLM model may need adjustment (check `OPENAI_MODEL` setting)
- Threshold too strict (try 0.7 instead of 0.8)

### Issue: Change Tracking Not Visible

**Check:**
1. Backend logs show `Fixed <criterion>: old → new` messages
2. SSE events are enabled (`requirement_updated` events)
3. Frontend is listening to SSE endpoint

## Monitoring

### Backend Logs

```bash
# Watch for change tracking
tail -f backend.log | grep "Fixed\|requirement_updated\|Iteration"

# Example output:
2025-11-25 22:29:29 - Fixed clarity: The system must authenticate... → As a user, I want to...
2025-11-25 22:29:39 - Fixed testability: As a user, I want to... → As a user, I want to...
2025-11-25 22:32:13 - Atomic criterion failed (score: 0.00), initiating split...
```

### Health Check

```bash
curl http://localhost:8087/health
# Returns: {"status": "healthy"}
```

### Runtime Config

```bash
curl http://localhost:8087/api/runtime-config
# Returns all effective settings including FIX_BATCH_SIZE, EARLY_EXIT_ON_GATING
```

## Best Practices

1. **Start with FIX_BATCH_SIZE=3**: Optimal balance of speed and API usage
2. **Enable EARLY_EXIT_ON_GATING**: Skip unnecessary work on failing requirements
3. **Use threshold=0.8**: Standard quality bar for production
4. **Monitor SSE events**: Real-time feedback on improvement progress
5. **Check logs**: Change tracking shows what's being fixed
6. **Batch 10-20 requirements**: Sweet spot for throughput
7. **Allow 5 iterations**: Gives time for iterative refinement
8. **Watch for atomic splits**: Multiple concepts = split requirement

## Related Documentation

- [ROUTES.md](ROUTES.md) - Full API reference
- [CONFIG.md](CONFIG.md) - Environment variables
- [DEMO.md](DEMO.md) - End-to-end examples
- [LLM-SPEC.md](LLM-SPEC.md) - LLM integration details
