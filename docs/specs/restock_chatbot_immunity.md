# Spec - Restock Chatbot Immunity & Truncation Removal

This specification details the enhancements to make the Instamart restock chatbot immune to various conversational edge cases and eliminate all item truncation behaviors.

## Goals
- **Eliminate All Slices/Truncations:** The chatbot must never show "+X more" or use `names[:3]` slices. Every low-stock item must be explicitly presented to the user.
- **Robust Singular/Plural Matcher:** Users typing `"tomato"`, `"egg"`, or `"milk"` must match `"Tomatoes (500g)"`, `"Nandini Eggs (Pack of 12)"`, and `"Amul Taza Milk 1L"` respectively, utilizing a bidirectional word-stem search.
- **Affirmative Expansion:** The chatbot must accept `"CONFIRM"`, `"CONFIRMED"`, `"PLACE ORDER"`, `"PROCEED"` as valid affirmatives on Turn 1.
- **Done-Stage Safety:** Prevent users from sending duplicate orders or getting errors by outputting a clear, friendly reminder if they reply to a completed checkout thread.

## Architecture & Data Flow

### 1. Unified Message Formatting
- **Alert Generation:** `restock.py` and `scheduler.py` will format the low-stock items list using a full join: `", ".join(names)`.
- **Cart Staging:** `restock_agent.py` will display all confirmed items: `", ".join(names)` without truncation.

### 2. Conversational Entry Router & State Machine
- When `state["stage"] == "done"`, the router directs the message to `parse_reply`.
- The `parse_reply` node detects that the order is completed and directly returns a status message without invoking LLM parsing or cart building.

### 3. Bidirectional Keyword Matching Algorithm
1. Retrieve user message, convert to lowercase, and split into words.
2. Strip all standard punctuation (`string.punctuation`) from each word.
3. Filter out common command verbs/stopwords (`"add"`, `"get"`, `"skip"`, etc.).
4. For each catalog item, check if any of the processed user words is a substring of the catalog name, or if any catalog keyword is a substring of the user's word.
5. Require words to be $\ge 3$ characters to prevent false matching.
