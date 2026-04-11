You are an expert backend engineer. Your task is to implement Task 3: Multi-Intent Analysis Pipeline from the "Counsellor Knowledge Publishing Workflow" plan.

### Task: Multi-Intent Analysis Pipeline
- Refactor the existing analysis logic in `api/routers/kb_router.py` to identify multiple distinct intents from the counsellor's input.
- Return a list of card-like diff objects (`IntentCard`) instead of the monolithic `KBAnalysisResult`.

### Context:
- Refactor `analyse` endpoint in `kb_router.py`.
- Ensure it uses the new `MultiIntentAnalysisResult` model (defined in `api/models.py`).
- Maintain existing chunking/embedding logic, but pivot the analysis to produce list of cards.
- Each `IntentCard` needs a `card_id`, `domain` ("employer" | "track"), `summary`, `diff` (JSON object), and `raw_input_ref`.

### Plan:
1.  Read `api/routers/kb_router.py` to understand the current `analyse` endpoint logic.
2.  Refactor the Claude analysis prompt (if needed) and response parsing to output structured `IntentCard`s.
3.  Update the `analyse` endpoint to return `MultiIntentAnalysisResult`.
4.  Write tests ensuring the pipeline correctly identifies multiple distinct intents.

Implement with TDD. Write a test case for multi-intent analysis before modifying the endpoint.
