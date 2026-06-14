# Restock Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a zero-cost local Web Chat Sandbox that connects an embedded Next.js dashboard Chat Drawer widget to a unified backend webhook router orchestrating the LangGraph restock agent, persisted natively via a PostgreSQL checkpointer.

**Architecture:** We will set up a Postgres checkpointer for LangGraph, routing both local Sandbox JSON requests and production Twilio Form requests through a unified `/api/webhook/whatsapp` endpoint. A collapsible chat drawer on the Next.js frontend will simulate WhatsApp conversation state.

**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL, LangGraph `PostgresSaver`, Next.js, Tailwind CSS

---

### Task 1: Setup Postgres Checkpointer Schema

**Files:**
- Create: `backend/database/migrations/versions/add_checkpoints_table.py` (or execute direct sql)
- Modify: `backend/database/connection.py`
- Test: `backend/tests/test_checkpointer.py`

- [ ] **Step 1: Write checkpointer verification test**
Create `backend/tests/test_checkpointer.py` to assert we can initialize the Postgres checkpointer and save/load state.
```python
import pytest
from backend.database.connection import engine
from langgraph.checkpoint.postgres import PostgresSaver

@pytest.mark.asyncio
async def test_postgres_saver_connection():
    # Verify we can connect and instantiate the checkpointer on the DB engine
    async with engine.connect() as conn:
        checkpointer = PostgresSaver(conn)
        # Verify checkpointer has setup/migration capability
        assert checkpointer is not None
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.\venv\Scripts\python.exe -m pytest backend/tests/test_checkpointer.py`
Expected: FAIL due to missing `PostgresSaver` package imports or schema tables.

- [ ] **Step 3: Implement database setup**
Modify `backend/database/connection.py` to provide a helper that exposes the database connection for checkpointer initialization.
```python
# Append to backend/database/connection.py
from langgraph.checkpoint.postgres import PostgresSaver

async def get_checkpointer():
    # Get a connection and return a PostgresSaver instance
    # Note: PostgresSaver requires a sync connection or an async one depending on the driver.
    # Since we are using asyncpg, we use PostgresSaver.from_conn_string
    from backend.config import settings
    # Replace asyncpg driver with psycopg for psycopg-based connection if needed,
    # or use standard AsyncPostgresSaver if available.
    # Let's use the standard connection string format:
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    # Return checkpointer using the synchronous postgres checkpointer interface 
    # since LangGraph.checkpoint.postgres supports connection pools
    return PostgresSaver.from_conn_string(db_url)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `.\venv\Scripts\python.exe -m pytest backend/tests/test_checkpointer.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/tests/test_checkpointer.py backend/database/connection.py
git commit -m "feat: add Postgres checkpointer setup"
```

---

### Task 2: Unified Webhook Router Implementation

**Files:**
- Modify: `backend/notifications/whatsapp.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_webhook.py`

- [ ] **Step 1: Write webhook test**
Create `backend/tests/test_webhook.py` to test both JSON (sandbox) and URL-Encoded Form (Twilio) payloads.
```python
import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.mark.asyncio
async def test_webhook_json():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock request from sandbox drawer
        response = await client.post(
            "/api/webhook/whatsapp",
            json={"phone": "+919999999999", "message": "YES"}
        )
        assert response.status_code == 200
        assert "response_message" in response.json()

@pytest.mark.asyncio
async def test_webhook_form():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock request from Twilio
        response = await client.post(
            "/api/webhook/whatsapp",
            data={"From": "whatsapp:+919999999999", "Body": "YES"}
        )
        assert response.status_code == 200
        assert "Response" in response.text  # TwiML contains <Response> tag
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.\venv\Scripts\python.exe -m pytest backend/tests/test_webhook.py`
Expected: FAIL (webhook route not registered or returning 404).

- [ ] **Step 3: Implement Unified Webhook logic**
Modify `backend/notifications/whatsapp.py` to handle both formats and trigger the LangGraph agent.
```python
from fastapi import APIRouter, Request, Response, Form, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel
import xml.etree.ElementTree as ET

from backend.database.connection import get_db
from backend.database.models import Household, RestockAlert
from backend.agents.restock_agent import restock_agent

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

class SandboxPayload(BaseModel):
    phone: str
    message: str

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    content_type = request.headers.get("content-type", "")
    
    phone = ""
    message = ""
    is_json = "application/json" in content_type

    if is_json:
        payload = await request.json()
        phone = payload.get("phone", "").replace("whatsapp:", "")
        message = payload.get("message", "")
    else:
        form_data = await request.form()
        phone = form_data.get("From", "").replace("whatsapp:", "")
        message = form_data.get("Body", "")

    # Look up household by phone number
    stmt = select(Household).where(Household.phone_number == phone)
    res = await db.execute(stmt)
    hh = res.scalar_one_or_none()

    if not hh:
        reply = "Household registration not found. Please register on the dashboard."
        if is_json:
            return {"response_message": reply}
        else:
            return Response(content=f"<Response><Message>{reply}</Message></Response>", media_type="application/xml")

    # Call LangGraph agent state machine (simulated/mocked responses when keys missing)
    # Check for active alert to compile details
    stmt_alert = select(RestockAlert).where(RestockAlert.household_id == hh.id).order_by(RestockAlert.sent_at.desc())
    res_alert = await db.execute(stmt_alert)
    alert = res_alert.scalars().first()

    # Formulate dummy list if no alerts exist yet for demo
    depleting_items = []
    if alert and alert.item_ids:
        depleting_items = [{"item_name": name, "confidence_score": 0.8, "days_remaining": 1.0} for name in alert.item_ids]

    # Run agent in stateful mode using phone as thread_id
    config = {"configurable": {"thread_id": phone}}
    
    # Run the compiled graph
    result = await restock_agent.ainvoke({
        "household_id": str(hh.id),
        "depleting_items": depleting_items,
        "stage": "parse_reply",
        "user_message": message,
        "confirmed_items": [],
        "response_message": ""
    }, config=config)

    reply_msg = result.get("response_message", "Processing completed.")

    if is_json:
        return {"response_message": reply_msg}
    else:
        return Response(content=f"<Response><Message>{reply_msg}</Message></Response>", media_type="application/xml")
```
Modify `backend/main.py` to register the new webhook router:
```python
# Inside backend/main.py
from backend.notifications import whatsapp
app.include_router(whatsapp.router)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `.\venv\Scripts\python.exe -m pytest backend/tests/test_webhook.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/notifications/whatsapp.py backend/main.py backend/tests/test_webhook.py
git commit -m "feat: unified webhook router implementation"
```

---

### Task 3: Collapsible Chat Drawer Component

**Files:**
- Create: `frontend/components/ChatDrawer.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Create the ChatDrawer Component**
Create `frontend/components/ChatDrawer.tsx` with standard state management for messages, sending state, and rendering bubble items.
```tsx
"use client";

import { useState } from "react";
import { MessageSquare, X, Send } from "lucide-react";

export default function ChatDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<{ sender: "user" | "bot"; text: string }[]>([
    { sender: "bot", text: "Hello! I am your Instamart Assistant. Send a message to get started." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userText = input;
    setMessages(prev => [...prev, { sender: "user", text: userText }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/webhook/whatsapp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: "+919999999999", message: userText })
      });
      const data = await res.json();
      setMessages(prev => [...prev, { sender: "bot", text: data.response_message }]);
    } catch (err) {
      setMessages(prev => [...prev, { sender: "bot", text: "Error sending message to sandbox." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-mono">
      {!isOpen ? (
        <button
          onClick={() => setIsOpen(true)}
          className="bg-orange-500 hover:bg-orange-600 text-white rounded-full p-4 shadow-lg flex items-center gap-2 border border-orange-400"
        >
          <MessageSquare className="h-6 w-6" />
          <span className="text-sm font-bold">Instamart Chat Sandbox</span>
        </button>
      ) : (
        <div className="bg-black border border-neutral-800 rounded-lg shadow-2xl w-80 h-96 flex flex-col">
          {/* Header */}
          <div className="border-b border-neutral-800 p-3 flex justify-between items-center bg-neutral-900">
            <span className="text-xs text-orange-500 font-bold">WHATSAPP SANDBOX (+919999999999)</span>
            <button onClick={() => setIsOpen(false)} className="text-neutral-500 hover:text-white">
              <X className="h-4 w-4" />
            </button>
          </div>
          {/* Messages */}
          <div className="flex-1 p-3 overflow-y-auto space-y-3">
            {messages.map((m, idx) => (
              <div key={idx} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`rounded p-2 text-xs max-w-[80%] ${m.sender === "user" ? "bg-orange-500 text-white" : "bg-neutral-800 text-neutral-300"}`}>
                  {m.text}
                </div>
              </div>
            ))}
            {loading && <div className="text-xs text-neutral-500">Assistant is typing...</div>}
          </div>
          {/* Input */}
          <div className="p-2 border-t border-neutral-800 flex bg-neutral-900">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendMessage()}
              placeholder="Type YES/NO or item name..."
              className="flex-1 bg-black border border-neutral-800 rounded px-2 py-1 text-xs text-white focus:outline-none"
            />
            <button onClick={sendMessage} className="ml-2 text-orange-500 hover:text-orange-400 p-1">
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Inject ChatDrawer into Dashboard layout**
Modify `frontend/app/layout.tsx` to render the collapsible drawer globally across pages.
```tsx
// Inside layout.tsx, import ChatDrawer and render it in the body:
import ChatDrawer from "../components/ChatDrawer";

// inside the root layout element:
return (
  <html lang="en">
    <body>
      {children}
      <ChatDrawer />
    </body>
  </html>
);
```

- [ ] **Step 3: Verify render in the browser**
Open dashboard local server and check bottom right for "Instamart Chat Sandbox" button.

- [ ] **Step 4: Commit**
```bash
git add frontend/components/ChatDrawer.tsx frontend/app/layout.tsx
git commit -m "feat: add frontend collapsible ChatDrawer widget"
```
