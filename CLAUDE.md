# PreFill — CLAUDE.md
# Global rules: C:\Users\kwakh\.gemini\config\AGENTS.md (read this first)
# Brain file: D:\workflow-main\brain\Projects\PreFill.md (full context)

---

## PROJECT RULES

### Database
- Always AsyncSession for SQLAlchemy. Sync SQLAlchemy blocks the FastAPI event loop.
- All DB queries in backend/api/routes/ — never direct DB calls in agents.
- Run pytest backend/tests/ -v after every backend change. All 16 must pass.

### Agents (LangGraph)
- Restock agent is in backend/agents/restock_agent.py — 5 graph nodes.
- Price agent: backend/agents/price_agent.py
- Recipe agent: backend/agents/recipe_agent.py
- LangGraph agent state MUST be saved with PostgreSQL checkpointer for persistence across restarts.
- Check backend/agents/ before writing new agent logic.

### MCP / Catalog
- Mock MCP server responses must stay synchronized with backend/seed/catalog.py.
- If you update catalog.py, update mock_server.py too. Both or neither.

### ML Pipeline
- ConsumptionModel uses Prophet (not scikit-learn linear regression) for time-series forecasting.
- ML models live in backend/ml/ — check before writing new prediction logic.
- Anomaly-excluded items (is_anomaly_excluded=True) must be filtered from ML training data.

### Notifications
- WhatsApp via backend/notifications/whatsapp.py.
- Scheduler: backend/notifications/scheduler.py (APScheduler).

### Before Marking Done
- pytest backend/tests/ -v -> all 16 pass.
- Verify mock MCP is in sync with catalog.py.
