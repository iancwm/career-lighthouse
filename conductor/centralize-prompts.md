# Centralize Prompts into prompts.yaml

Move all remaining LLM prompts from `api/cfg/model.yaml` to `api/cfg/prompts.yaml` and update the loading logic in `api/services/llm.py`.

## Proposed Changes

### Configuration

#### [api/cfg/prompts.yaml](api/cfg/prompts.yaml)
- Add `chat_system`, `disambiguation`, and `brief_system` prompts to the `prompts` section.
- Use literal block scalar (`|`) for consistent formatting and to preserve structure.

#### [api/cfg/model.yaml](api/cfg/model.yaml)
- Remove the `prompts` section and its three keys.

### Services

#### [api/services/llm.py](api/services/llm.py)
- Update `_prompts` initialization to load only from `prompts_cfg`.
- Fix `generate_brief` to correctly format `brief_system` with `school_name=SCHOOL_NAME`.

## Verification Plan

### Automated Tests
- Run existing tests to ensure no regressions in LLM functionality.
  ```bash
  pytest api/tests/test_chat_router.py
  pytest api/tests/test_brief_router.py
  pytest api/tests/test_kb_router.py
  pytest api/tests/test_session_router.py
  ```

### Manual Verification
- Inspect `llm_trace_log.jsonl` after running a brief generation or chat to ensure prompts are correctly loaded and formatted (i.e., no unexpanded `{school_name}` in the system prompt).
