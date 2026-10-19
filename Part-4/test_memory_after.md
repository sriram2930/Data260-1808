<!-- last_consolidated: 2026-10-19T10:25:54 -->
# MEMORY.md - Durable Facts (TEST FIXTURE: human-corrected after the pipeline's raw output)

- The primary domain entity is Course; the related entity is Department.
- The relational database is called s1808_rel; the document database added in HW6 is s1808_doc.
- The local model used for generation is qwen2.5:1.5b-instruct.
- The embedding model used for episodic memory and duplicate detection is all-MiniLM-L6-v2.
- SHORT_TERM_N default is 12. (HUMAN CORRECTION: the pipeline resolved this contradiction to "8, previously 12," which is wrong; the real codebase default in Part-1/memory.py is 12.)
- SUMMARIZE_EVERY_USER_MSGS is 5.
- The FastAPI backend runs on port 8008, computed as PORT_BASE = 8000 + (SID4 mod 900); previously misstated as port 9000, which the pipeline correctly resolved.
- SID4 for this student is 1808; PREFIX is s1808.
- Department deletion is blocked if courses reference it (the pipeline correctly resolved this from a contradiction stating it was "always allowed").
- Course fields: a unique course_code (format like CS-00001), course_title, and seats_available (default 30).
- The React client uses Redux Toolkit for state management, adopted in HW5 to replace plain useState.
- The MCP domain server exposes exactly three tools: search_courses, course_detail, department_stats.
- The meals MCP server is a tutorial exercise, not part of the core domain.
- Episodic memory stores up to 3 facts per user message, embedded and retrieved by cosine similarity.
- The safety rule in execute_tool caps search_courses at limit<=20; the agent loop has a max_steps ceiling.
- MongoDB collections for memory are messages, summaries, episodes; summaries have scope session or user, with a lifetime summary's session_id set to null.
- The announcements collection is the Part 1 document-oriented entity for HW6, with a status enum (draft/published/archived) and a category enum (course_update/enrollment/event/general).
- The retry policy from HW5 uses bounded exponential backoff, capped at 2 retries by default.
- The verify_hwNN.py scripts write a verification.json file; every homework tags the repository state as hwN.
- The GitHub repo is data260-1808, shared with two collaborators.
- Docker runs both the MySQL (host port 3307) and MongoDB (default port 27017) containers locally.
- AGENT.md stores durable project/agent instructions; MEMORY.md stores durable facts from previous conversations.
- Consolidation triggers when MEMORY.md exceeds 40 non-comment lines, or when it is more than 24 hours old.
- The /dream, /compact, /memory, and /help commands are implemented in Part-4/memory_cli.py.
- Token counts for the chat endpoint come from Ollama's own usage field; the per-component breakdown (primer/summary/short-term/episodic) is an estimate.
- The HW1 model adapter is Part-4/src/model_client.py's ModelClient class.
