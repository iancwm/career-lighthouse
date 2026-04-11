You are a spec compliance reviewer. Your task is to review the implementation against the "Counsellor Knowledge Publishing Workflow" plan.

### Review Task 1: Backend Session Storage
- Check for `KnowledgeSession` model in `api/models.py`.
- Check for `SessionStore` singleton in `api/services/session_store.py`.
- Verify storage is in `api/data/sessions/`.
- Ensure atomic operations and path safety.

Confirm the implementation matches the design and meets all requirements.
