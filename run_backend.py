import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
import uvicorn.config

# Monkeypatch uvicorn's loop factory resolver on Windows.
# This forces uvicorn to run with SelectorEventLoop instead of ProactorEventLoop,
# enabling compatibility with psycopg/asyncpg async connections.
if sys.platform == "win32":
    def patched_get_loop_factory(self):
        return asyncio.SelectorEventLoop
    uvicorn.config.Config.get_loop_factory = patched_get_loop_factory

from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)





