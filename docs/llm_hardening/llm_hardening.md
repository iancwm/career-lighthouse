Below is a minimal repo-specific spec you can hand to the coding agent. It is based on the current implementation in `api/services/llm.py`, `api/routers/kb_router.py`, and `api/config.py`, where the app already has timeout handling, tracing, and a multi-pass path for session intent extraction, but other LLM features still send oversized prompts or bypass the hardened call path. See `api/services/llm.py` for the current call wrappers and feature entrypoints, `api/routers/kb_router.py` for the KB/admin routes, `api/config.py` for runtime knobs, and `api/cfg/model.yaml` for token budgets and chunk settings.    

---

# Spec: harden all LLM-backed features against timeouts, malformed output, and oversized prompts

## Goal

Standardize every LLM feature in the repo so that it:

1. never sends unbounded raw input to Sonnet,
2. uses a shared guarded call path with explicit timeouts/retries/tracing,
3. uses schema-constrained extraction or staged generation instead of “one huge prompt”,
4. degrades gracefully with partial results instead of timing out or returning opaque failure.

---

## Current issues to fix

### 1) Not all LLM features use the hardened wrapper

There is already a shared `_call_with_trace()` / `_safe_create()` path in `api/services/llm.py` with timeout handling and structured tracing. However, `auto_complete_profile()` in `api/routers/kb_router.py` still instantiates `anthropic.Anthropic(...)` directly and calls `client.messages.create(...)` without the shared guardrails.  

### 2) Some features still pass too much text

`analyse_kb_input()` and `generate_track_draft()` build one-shot prompts from raw counsellor input plus retrieved excerpts, but they do not apply the same multi-pass logic that `generate_session_intents()` already uses for large inputs. `generate_brief()` and `chat_with_context()` also concatenate large KB chunks and history into a single call. 

### 3) Prompt budgets are too loose for some operations

`generate_session_intents()` is configured with `max_tokens_session_extraction: 8192`, `multi_pass_chunk_tokens: 15000`, and `multi_pass_overlap_tokens: 2000`. That is large and can still create long-running calls, especially when each chunk prompt also includes track/employer context and verbose chain-of-thought-like output. 

### 4) JSON extraction is fragile

Several functions rely on freeform text plus regex / fence stripping, then `json.loads()`. This is workable but brittle. The code currently retries once in `generate_session_intents()` if parsing fails, but the other extraction/generation paths do not consistently do staged repair. 

### 5) Retrieval is used, but not always in the right way

The repo already performs semantic retrieval from Qdrant for KB-backed tasks. That is a form of RAG. However, for extraction from a user-provided note/docx, the main issue is not “knowledge search” but “processing too much source text in one call.” RAG should remain for grounding against existing KB, but source-document extraction should be chunked/summarized first, then merged. `analyse()` and draft generation currently retrieve top chunks, but still feed the raw source text in one shot. 

---

## Required architecture changes

## A. Introduce a single LLM gateway for all features

Implement a single internal gateway layer and route every LLM call through it.

### Requirements

* All LLM features must call a shared function based on `_call_with_trace()`.
* No endpoint or service should directly instantiate `anthropic.Anthropic(...)` except in the shared client factory.
* Add per-operation config for:

  * timeout seconds
  * max retries
  * max input chars
  * max retrieved chunks
  * max excerpt chars per chunk
  * whether multi-pass is enabled
  * whether JSON repair retry is enabled

### Apply to these operations

* `chat_with_context()`
* `analyse_kb_input()`
* `generate_track_draft()`
* `generate_brief()`
* `generate_session_intents()`
* `auto_complete_profile()`

### Acceptance criteria

* `auto_complete_profile()` is refactored to use `llm_service` instead of raw Anthropic calls.
* Every LLM request produces trace entries in the same format.
* Timeout and connection failures return structured HTTP errors consistently.

---

## B. Enforce strict input budgets before model calls

Add a preprocessing stage for every LLM feature.

### Rules

* Never pass raw uploaded text directly to the LLM if it exceeds an operation-specific threshold.
* Add character limits in config for every feature.
* Add server-side truncation only as a last resort. Prefer chunking/multi-pass over blind truncation.
* Return a clear 422 only if the input is too large even after chunking policy, or if the operation explicitly requires small inputs.

### Suggested config additions

In `api/config.py` and/or YAML config:

* `llm_analyse_max_input_chars`
* `llm_track_draft_max_input_chars`
* `llm_brief_max_resume_chars`
* `llm_chat_max_context_chars`
* `llm_auto_complete_max_profile_chars`
* `llm_max_chunks_per_prompt`
* `llm_max_chunk_chars_for_prompt`

### Acceptance criteria

* No LLM feature can receive arbitrarily large docx/plaintext payloads.
* Large files are processed via chunking/multi-pass instead of a single prompt.

---

## C. Generalize multi-pass extraction beyond session intents

Take the existing multi-pass strategy in `generate_session_intents()` and reuse the pattern for other extraction/generation flows. The current code already chunks long text and recursively merges results for session intents; that pattern should become a reusable pipeline. 

### New internal pipeline

Implement a reusable function conceptually like:

`run_multi_pass_json_extraction(raw_text, operation_name, chunker_config, per_chunk_prompt_builder, merge_fn, validation_model)`

### Use it for

1. `analyse_kb_input()`

   * Per chunk: extract candidate profile updates, employer updates, new chunks, already-covered items
   * Merge: dedupe updates by slug+field, union chunks, union already-covered items
2. `generate_track_draft()`

   * Stage 1: extract normalized facts from chunks of counsellor input
   * Stage 2: synthesize draft JSON from merged facts + retrieved KB
3. `auto_complete_profile()`

   * Only if the profile content is large; otherwise keep single-pass
4. `generate_brief()`

   * Stage 1: compress resume and KB evidence separately
   * Stage 2: generate the brief from compact evidence

### Acceptance criteria

* `analyse_kb_input()` no longer fails on long notes/docx because of one-shot prompt size.
* `generate_track_draft()` can process long research notes without timing out.
* Merge logic is deterministic and unit tested.

---

## D. Switch extraction tasks to “evidence-first, schema-second”

For schema extraction, do not ask the model to directly transform huge raw text into final YAML-shaped JSON in one go.

### New pattern

For extraction-heavy features:

1. Split source text into chunks.
2. For each chunk, extract compact evidence objects:

   * normalized fact
   * target entity/slug
   * target field
   * confidence
   * source quote / excerpt
3. Merge evidence objects across chunks.
4. Run a second small LLM pass or deterministic mapper to produce final schema JSON.
5. Validate with Pydantic.
6. If invalid, run one repair pass on the already-small JSON only.

### Why

This reduces timeout risk and makes failures debuggable. It also avoids wasting tokens on repeatedly shipping the entire document and schema instructions in one prompt.

### Acceptance criteria

* `analyse_kb_input()` and `generate_track_draft()` are converted to evidence-first pipelines.
* Final model pass operates on compact merged evidence, not the full source document.

---

## E. Keep RAG, but use it only for grounding, not as the main fix for timeouts

### Decision

* Yes, keep RAG for grounding against the existing KB and employer/profile YAML knowledge.
* No, do not rely on RAG alone to solve timeouts from large uploaded documents.

### Implementation guidance

* For uploaded docx/raw text:

  * first chunk/process the source document itself,
  * then retrieve KB context relevant to each chunk or to the merged facts,
  * do not stuff both full source text and large retrieved KB excerpts into one prompt.
* For chat/brief features:

  * continue semantic retrieval,
  * but cap retrieved chunk count and per-chunk excerpt size.

### Specific changes

* In `analyse()` and draft generation routes, keep semantic retrieval from Qdrant, but retrieve less:

  * reduce top-k
  * compress excerpts
  * optionally retrieve per extracted entity rather than once for the whole raw document
* In `chat_with_context()` and `generate_brief()`:

  * cap number of KB chunks included
  * summarize or trim conversation history
  * enforce a total context character budget before the call

### Acceptance criteria

* KB retrieval remains in place.
* Large source files no longer cause oversized prompts because retrieval is no longer combined with full raw source indiscriminately.

---

## F. Tighten output contracts and repair flow

### Required changes

* All JSON-producing features must follow the same contract:

  1. first parse attempt,
  2. if parse fails, run one JSON-repair call on the model output only,
  3. if validation fails, run one schema-repair call on the parsed JSON only,
  4. if still invalid, return a structured 422 with a stable error code.

### Add helper functions

* `extract_json_block(text) -> str`
* `repair_json_output(raw_text, schema_name) -> dict`
* `validate_or_repair(parsed, pydantic_model) -> model`

### Acceptance criteria

* No feature retries the entire original large prompt just because JSON formatting failed.
* Repair calls are small and fast.

---

## G. Reduce token pressure and timeout defaults

The current config budgets are aggressive, especially for session extraction. Tune them down and rely more on chunking. `llm_timeout_seconds` is 30s and `llm_session_timeout_seconds` is 90s in config, while session extraction allows very large outputs.  

### Suggested defaults

* Standard JSON extraction timeout: 20–30s
* Large multi-pass per chunk timeout: 25–35s
* Remove or reduce any 90s single-call dependency
* Reduce `max_tokens_session_extraction` from 8192 to something materially smaller unless proven necessary
* Reduce `multi_pass_chunk_tokens` so each per-chunk request is predictably bounded
* Reduce overlap to the minimum needed for continuity

### Acceptance criteria

* Large document workflows rely on more smaller calls, not giant long calls.
* 504s become rare and localized to a chunk, not a whole operation.

---

## H. Add partial-result semantics for long jobs

### Required behavior

When processing a long document:

* if some chunks succeed and some fail, keep successful chunk results,
* mark failed chunks in trace metadata,
* return partial extraction if business-safe,
* otherwise return a structured error that says which phase failed.

### Good targets

* `generate_session_intents()`
* `analyse_kb_input()`
* `generate_track_draft()`

### Acceptance criteria

* One bad chunk does not zero out the entire workflow unless required for correctness.

---

## I. Add operation-specific observability

The trace layer already logs operation name, latency, input/output chars, and status. Extend metadata so failures are diagnosable by phase. 

### Add trace metadata fields

* `feature`
* `phase`
* `input_chars_pre_trim`
* `input_chars_sent`
* `kb_chunks_retrieved`
* `kb_chunks_sent`
* `chunk_index`
* `chunk_count`
* `parse_attempt`
* `repair_attempt`
* `partial_result`

### Acceptance criteria

* Admin can inspect why a timeout happened: too much source text, too many KB chunks, JSON repair loop, specific failing chunk, etc.

---

## J. Add tests for every LLM feature path

There are already tests around observability and AI flows in the repo; extend them to cover all LLM-backed features under failure conditions.  

### Add tests for

* oversized input triggers chunking, not one-shot send
* timeout on one chunk returns partial or structured failure
* malformed JSON triggers repair path
* `auto_complete_profile()` uses shared gateway
* `chat_with_context()` and `generate_brief()` cap context size
* draft generation with long input uses staged extraction
* analyse endpoint with long docx does not pass full raw text in one shot

### Acceptance criteria

* Unit tests cover prompt budgeting and repair logic.
* Integration tests cover representative long-input paths.

---

## Minimal implementation order

### Phase 1: stop the worst failure modes

1. Refactor `auto_complete_profile()` to use shared `llm_service`.
2. Add hard input budgets to every LLM feature.
3. Add generic JSON repair helper.
4. Reduce session extraction budgets and timeouts.

### Phase 2: fix architecture

5. Extract reusable multi-pass JSON pipeline.
6. Migrate `analyse_kb_input()` to multi-pass evidence-first extraction.
7. Migrate `generate_track_draft()` to staged extraction + synthesis.
8. Add context budgeting to chat and brief generation.

### Phase 3: polish

9. Add partial-result semantics.
10. Add expanded trace metadata and tests.

---

## Explicit answers to the architecture questions

### Do we use RAG?

Yes, but only for grounding against existing KB/employer/profile data. The repo already does this via vector search and retrieved chunks. Keep it. It is not the main fix for source-document timeout problems. Those need chunking, staged extraction, and prompt budgeting. 

### Do we enforce character limits?

Yes. Enforce server-side per-feature input limits. But do not treat “character limit” as the whole solution. The right policy is:

* small input: single pass,
* medium/large input: chunk + merge,
* extremely large input: reject or require async workflow later if you add jobs.

### What is the recommended architecture?

For extraction:

* parse file,
* normalize text,
* chunk source,
* per-chunk evidence extraction,
* merge evidence,
* optional KB retrieval for grounding,
* final schema synthesis,
* validate/repair,
* persist only after review.

For chat/brief:

* retrieve small grounded context,
* summarize/prune history,
* enforce total context budget,
* generate response with citations.