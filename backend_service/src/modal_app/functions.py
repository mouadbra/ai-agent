import os
import sqlite3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from .common import DB_PATH


def get_google_credentials() -> Credentials:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT access_token, refresh_token, token_expiry FROM google_tokens ORDER BY updated_at DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        access_token, refresh_token, token_expiry = row
        return Credentials(
            access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        )
    else:
        raise Exception("No stored Google credentials found.")


def schedule_meeting(
    meeting_title: str,
    start_time: str,
    end_time: str,
    attendees: list = None,
    location: str = None,
):
    creds = get_google_credentials()
    service = build("calendar", "v3", credentials=creds)
    event = {
        "summary": meeting_title,
        "location": location or "TBD",
        "description": "Scheduled by your virtual EA",
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"},
        "attendees": [{"email": email} for email in attendees] if attendees else [],
        "reminders": {"useDefault": True},
    }
    created_event = service.events().insert(calendarId="primary", body=event).execute()
    return created_event


def send_email(recipient: str, subject: str, body: str):
    creds = get_google_credentials()
    service = build("gmail", "v1", credentials=creds)
    message = MIMEText(body)
    message["to"] = recipient
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent


def read_emails(max_results: int = 5):
    creds = get_google_credentials()
    service = build("gmail", "v1", credentials=creds)
    results = service.users().messages().list(userId="me", maxResults=max_results).execute()
    messages = results.get("messages", [])
    emails = []
    for msg in messages:
        detail = service.users().messages().get(userId="me", id=msg["id"]).execute()
        headers = detail["payload"]["headers"]
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        snippet = detail.get("snippet", "")
        emails.append({"id": msg["id"], "subject": subject, "from": sender, "snippet": snippet})
    return emails


def read_calendar(max_results: int = 10):
    creds = get_google_credentials()
    service = build("calendar", "v3", credentials=creds)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


def edit_calendar(event_id: str, updates: dict):
    creds = get_google_credentials()
    service = build("calendar", "v3", credentials=creds)
    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    event.update(updates)
    updated_event = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
    return updated_event


def run_function(name: str, args: dict):
    if name == "schedule_meeting":
        return schedule_meeting(
            meeting_title=args["meeting_title"],
            start_time=args["start_time"],
            end_time=args["end_time"],
            attendees=args.get("attendees"),
            location=args.get("location"),
        )
    if name == "send_email":
        return send_email(
            recipient=args["recipient"],
            subject=args["subject"],
            body=args["body"],
        )
    if name == "read_emails":
        return read_emails(args.get("max_results", 5))
    if name == "read_calendar":
        return read_calendar(args.get("max_results", 10))
    if name == "edit_calendar":
        event_id = args.get("event_id")
        updates = args.get("updates", {})
        if not event_id:
            return {"error": "event_id is required"}
        if not updates:
            return {"error": "updates is required"}
        return edit_calendar(event_id=event_id, updates=updates)
    return None