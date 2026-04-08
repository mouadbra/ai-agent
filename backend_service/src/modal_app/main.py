import os
import json
import sqlite3
import modal
from modal import asgi_app
from fastapi import HTTPException
from pydantic import BaseModel
from google.oauth2.credentials import Credentials
from .common import DB_PATH, VOLUME_DIR, app, fastapi_app, volume, image
from .agent import process_agent_message
from dotenv import load_dotenv

load_dotenv()

# Request/Response models
class AgentRequest(BaseModel):
    message: str

class AgentResponse(BaseModel):
    response: str

class TokenData(BaseModel):
    access_token: str


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS google_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_expiry TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            messages TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


@fastapi_app.post("/agent/chat", response_model=AgentResponse)
async def agent_chat(request: AgentRequest):
    volume.reload()
    try:
        result = process_agent_message(request.message)
        volume.commit()
        return {"response": result}
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/agent/history")
def get_agent_history():
    try:
        volume.reload()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT messages FROM agent_threads ORDER BY updated_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"messages": []}
        messages = json.loads(row[0])
        chat_history = []
        for m in messages:
            if m.get("role") in ["user", "assistant"] and m.get("content"):
                chat_history.append({"role": m["role"], "text": m["content"]})
        return {"messages": chat_history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.delete("/agent/thread")
def delete_agent_thread():
    try:
        volume.reload()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agent_threads")
        conn.commit()
        conn.close()
        volume.commit()
        return {"message": "Agent thread deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.post("/auth/google/token")
def receive_token(token_data: TokenData):
    try:
        creds = Credentials(
            token_data.access_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        )
        refresh_token = creds.refresh_token if creds.refresh_token else ""
        token_expiry = creds.expiry.isoformat() if creds.expiry else ""
        volume.reload()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM google_tokens")
        cursor.execute(
            "INSERT INTO google_tokens (access_token, refresh_token, token_expiry) VALUES (?, ?, ?)",
            (token_data.access_token, refresh_token, token_expiry),
        )
        conn.commit()
        conn.close()
        volume.commit()
        return {
            "access_token": token_data.access_token,
            "refresh_token": refresh_token,
            "token_expiry": token_expiry,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Always last
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ai-agent-secret")],
    volumes={VOLUME_DIR: volume},
)
@asgi_app()
def fastapi_entrypoint():
    init_db()
    return fastapi_app