# AI Executive Assistant Agent

A virtual executive assistant powered by GPT-4o that chats in natural language and autonomously manages your Google Calendar and Gmail — scheduling meetings, sending emails, and reading your agenda.

## Overview

This application allows you to:

- Chat in natural language with an AI assistant backed by **Azure OpenAI GPT-4o**
- Let the agent automatically decide which tool to use (schedule, email, read calendar...)
- Create calendar events in **Google Calendar** without leaving the chat
- Send and read emails via **Gmail**
- Persist conversation history across sessions in **SQLite**
- Connect and disconnect your Google account via **OAuth 2.0**
- Reset the conversation thread to start fresh at any time

## Technical Architecture

- **Frontend**: React + TypeScript + Tailwind + Shadcn/ui
  - OAuth Google Connect / Disconnect button
  - Chat interface with Markdown-rendered message bubbles
  - Thread reset button
  - Loads Google API (`gapi`) and Google Identity Services (`gis`) dynamically

- **Backend**: FastAPI + Modal
  - `/agent/chat` → process user message through the agent loop
  - `/agent/history` → retrieve full conversation history
  - `/agent/thread` (DELETE) → reset conversation thread
  - `/auth/google/token` → receive and store OAuth access token

- **Agent Logic**: Azure OpenAI GPT-4o with function calling
  - Conversation history stored in SQLite
  - 5 tools: `schedule_meeting`, `send_email`, `read_emails`, `read_calendar`, `edit_calendar`

- **Database**: SQLite on Modal Volume
  - `google_tokens`: OAuth credentials
  - `agent_threads`: persistent conversation history

- **LLM**: Azure OpenAI GPT-4o

- **Infrastructure**: Modal for serverless deployment with persistent volume

## Code Structure

```
ai_agent/
│
├── backend_service/
│   ├── .env                          # Azure + Google credentials (not committed)
│   ├── pyproject.toml
│   └── src/modal_app/
│       ├── common.py                 # Modal app, FastAPI instance, CORS, image
│       ├── agent.py
│       │   ├── get_code_prompt()     # System prompt with current date
│       │   ├── get_or_create_thread() # Load conversation history from SQLite
│       │   ├── save_thread()         # Persist conversation history
│       │   └── process_agent_message() # Core agent loop (tool calls)
│       ├── functions.py
│       │   ├── get_google_credentials() # Load OAuth creds from SQLite
│       │   ├── schedule_meeting()    # Google Calendar event creation
│       │   ├── send_email()          # Gmail send
│       │   ├── read_emails()         # Gmail inbox read
│       │   ├── read_calendar()       # Google Calendar read
│       │   ├── edit_calendar()       # Google Calendar event edit
│       │   └── run_function()        # Tool name → Python function dispatcher
│       └── main.py
│           ├── init_db()             # Create SQLite tables
│           ├── POST /agent/chat      # Process user message
│           ├── GET /agent/history    # Get conversation history
│           ├── DELETE /agent/thread  # Reset conversation
│           └── POST /auth/google/token # Store OAuth token
│
└── frontend_service/
    ├── .env                          # VITE_MODAL_URL, VITE_GOOGLE_CLIENT_ID, etc.
    └── src/
        ├── App.tsx                   # Main component
        └── components/ui/
            ├── button.tsx
            └── card.tsx
```

## Database

### Table 1: Google Tokens
```sql
CREATE TABLE google_tokens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    access_token  TEXT NOT NULL,
    refresh_token TEXT,
    token_expiry  TEXT,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table 2: Agent Threads
```sql
CREATE TABLE agent_threads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    messages   TEXT NOT NULL,       -- JSON array of conversation messages
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Agent Loop

```
User message
     ↓
Load conversation history from SQLite
     ↓
Add system prompt (with current date) if first message
     ↓
Call GPT-4o with tools defined
     ↓
Tool call required?
  ├── Yes → run_function(name, args)
  │         → schedule_meeting / send_email / read_emails / read_calendar / edit_calendar
  │         → add tool result to messages
  │         → call GPT-4o again
  └── No  → return final response
     ↓
Save conversation history to SQLite
```

## Available Tools (Function Calling)

| Tool | Description | Google API |
|------|-------------|------------|
| `schedule_meeting` | Create a calendar event with title, start/end time, attendees | Calendar v3 |
| `send_email` | Send an email to a recipient | Gmail v1 |
| `read_emails` | Fetch the N most recent inbox messages | Gmail v1 |
| `read_calendar` | List upcoming calendar events | Calendar v3 |
| `edit_calendar` | Update an existing calendar event | Calendar v3 |

## Technologies Used

### Backend

- **FastAPI**: Python web framework
- **Modal**: Serverless deployment with persistent volume
- **SQLite**: Conversation history and OAuth token persistence
- **Azure OpenAI GPT-4o**: Agent LLM with function calling
- **Google APIs**: Calendar v3 and Gmail v1
- **Pydantic**: Request/response validation

### Frontend

- **React + TypeScript**: UI framework
- **Vite**: Build tool
- **TailwindCSS**: Styling
- **Shadcn/ui**: UI components (Button, Card)
- **react-markdown**: Render agent responses as Markdown
- **Google API Client Library**: OAuth 2.0 flow

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/mouadbra/ai-agent.git
cd ai-agent
```

### 2. Google Cloud Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → New Project
2. Enable **Google Calendar API** and **Gmail API**
3. Create **OAuth 2.0 credentials** (Web application):
   - Authorized JavaScript origins: `http://localhost:5173`
   - Authorized redirect URIs: `http://localhost:5173`
4. Add yourself as a **Test user** in OAuth consent screen
5. Create an **API Key** restricted to Calendar API + Gmail API

### 3. Backend

```bash
cd backend_service
uv sync
```

Create a `.env` file:
```
AZURE_OPENAI_CHAT_API_KEY=
AZURE_OPENAI_CHAT_ENDPOINT=
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

Create a Modal secret named `ai-agent-secret` with the same variables at [modal.com](https://modal.com).

Authenticate with Modal:
```bash
python -m modal token new
```

Run the backend:
```bash
uv run modal serve -m src.modal_app.main
```

### 4. Frontend

```bash
cd frontend_service
bun install
```

Create a `.env` file:
```
VITE_MODAL_URL=https://your-modal-url.modal.run
VITE_GOOGLE_CLIENT_ID=
VITE_GOOGLE_API_KEY=
VITE_GOOGLE_SCOPES=https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.modify
```

Run the frontend:
```bash
bun run dev
```

## Typical Flow

1. Open `http://localhost:5173/`
2. Click **Connect Google** → complete the OAuth flow
3. Try: *"What's on my calendar this week?"*
4. Try: *"Schedule a meeting called Team Sync tomorrow at 2pm UTC for 1 hour"*
5. Try: *"Send an email to alice@example.com about the project update"*
6. Click **Reset Thread** to start a fresh conversation

## Usage / Demo
- The video shows complete usage: Google authentication, scheduling meetings, sending emails, and multi-turn conversation
- Watch the demo here: [AI Executive Assistant Demo]()

## Notes

- Google OAuth tokens are valid for **1 hour** — reconnect if the agent returns auth errors
- The agent always receives the current date/time in its system prompt to avoid scheduling events in the past
- Conversation history persists across browser sessions via SQLite — use **Reset Thread** to clear it
- The LLM never directly touches the database — all Google API calls go through typed Python functions
