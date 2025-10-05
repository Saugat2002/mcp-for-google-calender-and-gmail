#!/usr/bin/env python3

import json
import base64
from email.mime.text import MIMEText
from fastmcp import FastMCP
from google_service_utils import GoogleServiceBase, initialize_google_service, get_timezone_info, convert_date_to_user_timezone
import pytz

mcp = FastMCP("gmail-mcp-server")

class GmailService(GoogleServiceBase):
    def __init__(self):
        super().__init__('gmail', 'v1', [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify"
        ])
    
    def _get_user_timezone(self):
        import os
        manual_tz = os.getenv('USER_TIMEZONE')
        self.user_timezone = pytz.timezone(manual_tz) if manual_tz else pytz.timezone('Asia/Kathmandu')
    
    def _extract_body(self, payload):
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
                elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        else:
            if payload['mimeType'] == 'text/plain' and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        return body
    
    def _create_message(self, to: str, subject: str, body: str):
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')}

gmail_service = GmailService()

@mcp.tool()
def get_gmail_timezone_info():
    if not gmail_service.service:
        initialize_google_service(gmail_service, "Gmail", gmail_service.scopes)
    return get_timezone_info(gmail_service)

@mcp.tool()
def search_emails(query: str = "", max_results: int = 10):
    if not gmail_service.service:
        initialize_google_service(gmail_service, "Gmail", gmail_service.scopes)
    results = gmail_service.service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    emails = []
    for message in results.get('messages', []):
        msg = gmail_service.service.users().messages().get(userId='me', id=message['id']).execute()
        headers = msg['payload'].get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
        date_user = convert_date_to_user_timezone(date, gmail_service.get_user_timezone())
        body = gmail_service._extract_body(msg['payload'])
        emails.append({
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date_user,
            'body': body[:500] + '...' if len(body) > 500 else body,
            'snippet': msg.get('snippet', '')
        })
    return json.dumps(emails, indent=2)

@mcp.tool()
def get_email(message_id: str):
    if not gmail_service.service:
        initialize_google_service(gmail_service, "Gmail", gmail_service.scopes)
    msg = gmail_service.service.users().messages().get(userId='me', id=message_id).execute()
    headers = msg['payload'].get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
    date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
    to = next((h['value'] for h in headers if h['name'] == 'To'), '')
    date_user = convert_date_to_user_timezone(date, gmail_service.get_user_timezone())
    body = gmail_service._extract_body(msg['payload'])
    return json.dumps({
        'id': message_id,
        'subject': subject,
        'sender': sender,
        'to': to,
        'date': date_user,
        'body': body,
        'snippet': msg.get('snippet', '')
    }, indent=2)

@mcp.tool()
def send_email(to: str, subject: str, body: str):
    if not gmail_service.service:
        initialize_google_service(gmail_service, "Gmail", gmail_service.scopes)
    message = gmail_service._create_message(to, subject, body)
    sent_message = gmail_service.service.users().messages().send(userId='me', body=message).execute()
    return json.dumps({
        "success": True,
        "message_id": sent_message['id'],
        "message": "Email sent successfully"
    }, indent=2)

if __name__ == "__main__":
    mcp.run()