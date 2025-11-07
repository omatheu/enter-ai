# Quick Reference: Performance Bottlenecks & Fixes

## Critical Metrics
- **Total Backend Code**: 1,304 lines
- **Current Extraction Time**: ~1750ms (10 fields, 20KB PDF)
- **LLM Latency**: ~800ms (unavoidable)
- **Local Processing**: ~950ms (optimizable)
- **Optimization Potential**: 15-25% of total time (140-300ms)

---

## QUICK FIX CHECKLIST (Effort: < 2 hours)

### 1. Pre-compile Heuristic Regexes (10 min)
**File**: `backend/app/extractors/heuristics.py`
**Change**: Convert PATTERNS dict strings to compiled regex objects
**Savings**: 30-60ms per extraction
```python
# Before:
PATTERNS = {"cpf": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"}

# After:
PATTERNS = {"cpf": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", re.IGNORECASE)}
```

### 2. Add Schema Learner Size Limit (15 min)
**File**: `backend/app/schema/patterns.py`
**Change**: Add max_size with LRU eviction and truncate examples
**Savings**: Prevents unbounded memory growth
```python
class SchemaLearner:
    def __init__(self, max_labels: int = 1000, max_example_len: int = 100):
        self.learned = {}
        self.max_labels = max_labels
        self.max_example_len = max_example_len
    
    def learn_from_result(self, ...):
        # Truncate example to max_example_len
        example = value[:self.max_example_len]
        # Evict oldest label if max_labels exceeded
```

### 3. Optimize LLM Prompt (10 min)
**File**: `backend/app/extractors/llm_extractor.py`
**Change**: Remove redundant instructions
**Savings**: 20-40 tokens per call
```python
# Before (80 tokens):
prompt = "You are an assistant that extracts structured information from PDF text. Return a JSON object mapping each requested field to its extracted value. If a value cannot be found, return null. Only respond with valid JSON."

# After (15 tokens):
prompt = "Extract requested fields to JSON."
```

### 4. Pre-compile Validator Regexes (5 min)
**File**: `backend/app/extractors/validator.py`
**Change**: Add `DIGITS_ONLY_REGEX = re.compile(r"\D")`
**Savings**: 5-10ms
```python
class Validator:
    DIGITS_ONLY_REGEX = re.compile(r"\D")  # Add this
    
    @staticmethod
    def validate_cpf(value: str) -> bool:
        if Validator.CPF_REGEX.match(value):
            digits = Validator.DIGITS_ONLY_REGEX.sub("", value)  # Use this
```

### 5. Move PDF Hashing to Thread Pool (15 min)
**File**: `backend/app/services/extraction.py`
**Change**: Make `_hash_pdf()` async and use `run_in_executor()`
**Savings**: 50-100ms (unblocks event loop)
```python
@staticmethod
async def _hash_pdf(pdf_path: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ExtractionService._hash_pdf_sync, pdf_path)
```

---

## MEDIUM EFFORT IMPROVEMENTS (2-4 hours)

### 6. Parallelize PDF Text + Tables (30 min)
**File**: `backend/app/services/extraction.py` lines 76-82
**Change**: Use `asyncio.gather()` for parallel extraction
**Savings**: 100-200ms
```python
# Before:
text = self.pdf_extractor.extract_text(request.pdf_path)
tables = self.pdf_extractor.extract_tables(request.pdf_path)

# After:
loop = asyncio.get_event_loop()
text_task = loop.run_in_executor(None, self.pdf_extractor.extract_text, request.pdf_path)
tables_task = loop.run_in_executor(None, self.pdf_extractor.extract_tables, request.pdf_path)
text, tables = await asyncio.gather(text_task, tables_task)
```

### 7. Batch Recovery LLM Calls (2 hours)
**Files**: `backend/app/services/extraction.py` + `backend/app/extractors/error_recovery.py`
**Change**: Instead of calling LLM once per field in recovery, batch all failed fields
**Savings**: 300-600ms
**Complexity**: High - requires refactoring recovery flow

Key insight:
- Current: 5 failed fields = 5 LLM calls in recovery
- Better: 5 failed fields = 1 batched LLM call in recovery

### 8. Optimize Context Building (1.5 hours)
**File**: `backend/app/utils/context.py`
**Changes**:
1. Deduplicate keywords before searching
2. Use single compiled regex with all keywords
3. Cache tokenized schema
**Savings**: 50-100ms

---

## ARCHITECTURAL IMPROVEMENTS (4+ hours)

### 9. Async PDF Extraction
**File**: `backend/app/extractors/pdf_extractor.py`
**Change**: Wrap synchronous pdfplumber calls in thread pool
**Benefit**: Remove sync blocking from async pipeline
**Complexity**: Requires significant refactoring

### 10. Distributed Caching (Redis)
**Files**: `backend/app/cache/`
**Change**: Add Redis backing to memory cache
**Benefit**: Persist cache across restarts, multi-instance support
**Complexity**: High - requires Redis infrastructure

### 11. Batch Recovery Improvements
**File**: `backend/app/services/extraction.py`
**Change**: Implement multi-batch strategy for large schemas
**Benefit**: Handle 100+ fields efficiently

---

## PERFORMANCE IMPACT SUMMARY

| Fix | Priority | Effort | Savings | Status |
|-----|----------|--------|---------|--------|
| Pre-compile heuristics | P0 | 10m | 30-60ms | Easy |
| Schema learner limit | P0 | 15m | Memory | Easy |
| Optimize prompt | P0 | 10m | 20-40 tokens | Easy |
| Validator regex | P0 | 5m | 5-10ms | Easy |
| PDF hashing async | P1 | 15m | 50-100ms | Easy |
| PDF parallel extraction | P1 | 30m | 100-200ms | Easy |
| Batch recovery | P1 | 2h | 300-600ms | Medium |
| Optimize context building | P2 | 1.5h | 50-100ms | Medium |
| Async PDF extractor | P2 | 3h | 150-300ms | Hard |
| Redis cache | P3 | 4h | Restart benefit | Hard |

**Total Time with All Tier 1 Fixes**: 55 minutes
**Potential Savings**: 200-450ms (12-25%)

---

## MONITORING & PROFILING

The system already has good profiling in place:
```python
# File: backend/app/utils/profiling.py
# Tracks:
- total_ms
- pdf_text_ms
- pdf_tables_ms
- heuristics_ms
- validation_ms
- llm_batch_ms
- recovery_ms
- llm_ms (aggregate)
```

Use profiling output to validate improvements:
```json
{
  "profiling": {
    "total_ms": 1750,
    "pdf_text_ms": 200,
    "pdf_tables_ms": 150,
    "heuristics_ms": 60,
    "validation_ms": 40,
    "llm_batch_ms": 800,
    "recovery_ms": 300,
    "llm_ms": 1100
  }
}
```

---

## FILES TO MODIFY (In Priority Order)

### Tier 1 (High Impact, Low Effort)
1. `backend/app/extractors/heuristics.py` - Pre-compile regexes
2. `backend/app/schema/patterns.py` - Add size limit
3. `backend/app/extractors/llm_extractor.py` - Optimize prompt
4. `backend/app/extractors/validator.py` - Pre-compile inline regex
5. `backend/app/services/extraction.py` - Async PDF hashing

### Tier 2 (High Impact, Medium Effort)
6. `backend/app/services/extraction.py` - Parallel PDF extraction
7. `backend/app/extractors/error_recovery.py` - Batch recovery calls
8. `backend/app/utils/context.py` - Optimize keyword search

### Tier 3 (Architectural)
9. `backend/app/extractors/pdf_extractor.py` - Thread pool wrapper
10. `backend/app/cache/` - Redis integration

---

## TESTING IMPROVEMENTS

After each fix, measure impact using:

```bash
# Run profiled extraction
pytest tests/test_service_with_stub.py -v

# Check profiling output in response metadata:
# - Look for reduced "heuristics_ms", "pdf_text_ms", "pdf_tables_ms"
# - Validate "total_ms" decreased
```

---

## KEY INSIGHTS

1. **LLM Latency Dominates**: ~800ms of 1750ms is OpenAI API
   - Optimizations affect the other 950ms
   - Max improvement without architecture change: ~20-30%

2. **Recovery is Biggest Win**: Batching recovery calls saves 300-600ms
   - Currently: 1 batch call + N recovery calls
   - Should be: 1 batch call + 1 recovery call

3. **Already Partially Optimized**:
   - PDF content caching ✓
   - Recovery parallelization ✓
   - Batch field extraction ✓

4. **Quick Wins Available**:
   - 5 improvements under 30 minutes each
   - Combined savings: 150-250ms

5. **Memory Not a Current Issue**:
   - Schema learner could grow large but unlikely in typical use
   - Cache is in-memory only but efficient

---

## RECOMMENDED NEXT STEPS

1. **Week 1**: Implement Tier 1 fixes (55 minutes total)
   - Expected improvement: 150-250ms
   - Test with `pytest tests/`
   - Merge to feature branch

2. **Week 2**: Implement Tier 2 fixes
   - Focus on recovery batching first (biggest impact)
   - Then PDF parallelization
   - Expected improvement: 300-500ms

3. **Week 3+**: Consider Tier 3 based on bottleneck analysis
   - Only pursue if additional 100ms savings needed
   - Requires significant refactoring

