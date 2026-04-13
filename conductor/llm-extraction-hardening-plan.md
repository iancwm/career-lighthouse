# Plan: Improving Long Document Extraction & Observability

Improve LLM performance on extracting intents from large documents and provide better observability into the LLM's thinking process.

## Background & Motivation
The current intent extraction uses a single LLM call with a 4096-token output limit and no explicit "thinking" step. For longer documents (like the 15k-character counsellor memos), the LLM may become "lazy," miss intents, or truncate its JSON output. Users also lack visibility into *why* certain intents were extracted or missed.

## Proposed Changes

### 1. Model & API Updates
- **`api/models.py`**:
    - Add `thought: Optional[str] = None` to `KnowledgeSession`.
    - Add `thought: Optional[str] = None` to `SessionAnalysisResponse`.
    - Add `thought: Optional[str] = None` to `MultiIntentAnalysisResult` (if used).
- **`api/routers/session_router.py`**:
    - Update `analyze_session` to capture the `thought` from the LLM service and store it in the session.

### 2. LLM Service Enhancements (`api/services/llm.py`)
- **Thinking Process:**
    - Update the `generate_session_intents` system prompt to require a `<thought>` block before the JSON output.
    - Instructions for the thought block: Analyze the document section by section, identifying key entities and changes.
- **Robust Parsing:**
    - Use regex to extract the `<thought>` block and the JSON object separately.
    - Handle cases where the LLM might only output one or the other.
- **Handling Large Documents (Scaling):**
    - If input text exceeds 30,000 characters (~8k-10k tokens), switch to a **multi-pass extraction strategy**:
        1. Split document into overlapping chunks (using existing `chunk_text`).
        2. Extract intents from each chunk.
        3. Merge and deduplicate results.
- **Output Capacity:**
    - Increase `max_tokens` from 4096 to **8192** (supported by Claude 3.5 Sonnet) to prevent truncation of long JSON results.

### 3. Observability & Logging
- Log the number of intents extracted and whether multi-pass was used.
- Ensure the `thought` is surfaced to the frontend for admin review.

## Implementation Steps

### Task 1: Update Models & API Schema
1. Modify `api/models.py` to include `thought` in relevant Pydantic models.
2. Update `api/routers/session_router.py` to handle the new field.

### Task 2: Refactor LLM Extraction Logic
1. Update `generate_session_intents` in `api/services/llm.py`:
    - Implement thought-block requirement and parsing.
    - Increase `max_tokens`.
    - Add logic to check document length and decide between single-pass vs. multi-pass.
2. Implement `_merge_intents` helper to deduplicate cards.

### Task 3: Verification
1. Run `api/tests/test_session_intents.py` and `api/tests/test_session_router.py`.
2. Add a new test case for "large document" (mocked) to verify multi-pass logic.
3. Manually test with one of the `demo-data/meeting-notes/` DOCX files.

## Verification & Testing

### Test Coverage Diagram
```
CODE PATH COVERAGE
===========================
[+] api/services/llm.py
    │
    ├── generate_session_intents()
    │   ├── [GAP] Single-pass with <thought> block — needs test
    │   ├── [GAP] Multi-pass for long documents — needs test
    │   └── [GAP] Error handling (invalid JSON/thought) — needs test
    │
    └── _merge_intents()
        └── [GAP] Deduplication logic — needs test

[+] api/routers/session_router.py
    │
    └── analyze_session()
        └── [GAP] Store/return thought field — needs test

─────────────────────────────────
COVERAGE: 0/5 new paths tested (0%)
─────────────────────────────────
```

## Not in Scope
- UI changes to display the `thought` (assumed to be handled in a follow-up or that the frontend will automatically surface it if added to the response).
- Changing the underlying LLM model (staying with Claude 3.5 Sonnet).
- Rewriting the DOCX parser (current one is sufficient).
