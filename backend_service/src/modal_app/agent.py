import os
import json
import sqlite3
from openai import AzureOpenAI
from .common import DB_PATH
from .functions import run_function
from datetime import datetime, timezone

def get_code_prompt():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
You are a virtual executive assistant. You help users manage their schedule and emails.
Today's date and time is: {now}

You have access to the following tools:
- schedule_meeting: Create a calendar event
- send_email: Send an email
- read_emails: Read recent emails
- read_calendar: Read upcoming calendar events
- edit_calendar: Edit an existing calendar event

Always be concise and professional. When you need to use a tool, use it directly.
When scheduling meetings, always use ISO 8601 format for dates (e.g. 2026-04-08T14:00:00Z).
If you need more information to complete a task, ask the user.
"""

functions = [
    {
        "name": "schedule_meeting",
        "description": "Create a new calendar event",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_title": {"type": "string", "description": "Title of the meeting"},
                "start_time": {"type": "string", "description": "Start time in ISO 8601 format (e.g. 2024-01-15T10:00:00Z)"},
                "end_time": {"type": "string", "description": "End time in ISO 8601 format"},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee emails"},
                "location": {"type": "string", "description": "Location of the meeting"},
            },
            "required": ["meeting_title", "start_time", "end_time"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email to a recipient",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Email address of the recipient"},
                "subject": {"type": "string", "description": "Subject of the email"},
                "body": {"type": "string", "description": "Body of the email"},
            },
            "required": ["recipient", "subject", "body"],
        },
    },
    {
        "name": "read_emails",
        "description": "Read recent emails from inbox",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Maximum number of emails to retrieve"},
            },
        },
    },
    {
        "name": "read_calendar",
        "description": "Read upcoming calendar events",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Maximum number of events to retrieve"},
            },
        },
    },
    {
    "name": "edit_calendar",
    "description": "Edit an existing calendar event. You must provide both the event_id and the updates dict containing the fields to change (e.g. {'attendees': [{'email': 'alice@example.com'}], 'summary': 'New Title'})",
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "ID of the event to edit"},
            "updates": {
                "type": "object",
                "description": "Fields to update. Example: {'attendees': [{'email': 'alice@example.com'}], 'location': 'Google Meet'}",
            },
        },
        "required": ["event_id", "updates"],
    },
    },
]


def get_or_create_thread(conn) -> list:
    cursor = conn.cursor()
    cursor.execute("SELECT messages FROM agent_threads ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        return json.loads(row[0])
    return []


def save_thread(conn, messages: list):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agent_threads")
    cursor.execute(
        "INSERT INTO agent_threads (messages) VALUES (?)",
        (json.dumps(messages),)
    )
    conn.commit()


def process_agent_message(user_message: str) -> str:
    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_CHAT_API_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_CHAT_ENDPOINT"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )

    conn = sqlite3.connect(DB_PATH)
    messages = get_or_create_thread(conn)

    # Add system prompt if first message
    if not messages:
        messages.append({"role": "system", "content": get_code_prompt()})

    # Add user message
    messages.append({"role": "user", "content": user_message})

    # Agent loop
    while True:
        response = client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
            messages=messages,
            tools=[{"type": "function", "function": f} for f in functions],
            tool_choice="auto",
        )

        message = response.choices[0].message
        messages.append(message.model_dump())

        # No tool call → return response
        if not message.tool_calls:
            save_thread(conn, messages)
            conn.close()
            return message.content

        # Execute tool calls
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"Calling tool: {name} with args: {args}")
            result = run_function(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })