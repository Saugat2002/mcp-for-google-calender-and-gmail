#!/usr/bin/env python3

import json
import base64
import os
import logging
from typing import Dict, List
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastmcp import FastMCP

mcp = FastMCP("gmail-mcp-server")
logger = logging.getLogger(__name__)

class GmailService:
    def __init__(self):
        self.service = None
        self.credentials = None
    
    def authenticate(self, credentials_path: str, token_path: str):
        try:
            with open(credentials_path, 'r') as f:
                creds_data = json.load(f)
            
            with open(token_path, 'r') as f:
                token_data = json.load(f)
            
            self.credentials = Credentials(
                token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes', [])
            )
            
            self.service = build('gmail', 'v1', credentials=self.credentials)
            logger.info("Gmail API authenticated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Gmail authentication failed: {str(e)}")
            return False
    
    def authenticate_with_token_data(self, credentials_path: str, token_data: dict):
        try:
            with open(credentials_path, 'r') as f:
                creds_data = json.load(f)
            
            self.credentials = Credentials(
                token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes', [])
            )
            
            self.service = build('gmail', 'v1', credentials=self.credentials)
            logger.info("Gmail API authenticated successfully with token data")
            return True
            
        except Exception as e:
            logger.error(f"Gmail authentication with token data failed: {str(e)}")
            return False
    
    def _extract_body(self, payload: Dict) -> str:
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        else:
            if payload['mimeType'] == 'text/plain' and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        
        return body
    
    def _create_message(self, to: str, subject: str, body: str) -> Dict:
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        return {
            'raw': raw_message
        }

gmail_service = GmailService()

def initialize_gmail_service():
    try:
        credentials_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS", "/Users/saugatadhikari/Saugat/WORK/IBRIZ/AssesmentTask/mcpproject/backend/gcp-oauth.keys.json")
        token_string = os.getenv("GOOGLE_ACCESS_TOKEN", "")
        
        if not token_string:
            logger.warning("No Gmail token found in environment. Gmail service will not be authenticated.")
            return False
        
        if not os.path.exists(credentials_path):
            logger.warning(f"Gmail credentials file not found at {credentials_path}")
            return False
        
        try:
            token_data = json.loads(token_string)
        except json.JSONDecodeError:
            token_data = {
                "access_token": token_string,
                "refresh_token": None,
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": None,
                "client_secret": None,
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.modify"]
            }
            logger.info("Using access token string directly")
        
        success = gmail_service.authenticate_with_token_data(credentials_path, token_data)
        if success:
            logger.info("Gmail service authenticated successfully")
        else:
            logger.error("Failed to authenticate Gmail service")
        
        return success
        
    except Exception as e:
        logger.error(f"Error initializing Gmail service: {str(e)}")
        return False

def reinitialize_gmail_service():
    global gmail_service
    try:
        gmail_service = GmailService()
        return initialize_gmail_service()
    except Exception as e:
        logger.error(f"Error reinitializing Gmail service: {str(e)}")
        return False

initialize_gmail_service()

@mcp.tool()
def search_emails(query: str = "", max_results: int = 10) -> str:
    try:
        if not gmail_service.service:
            return json.dumps({"error": "Gmail service not authenticated"})
        
        results = gmail_service.service.users().messages().list(
            userId='me', 
            q=query, 
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for message in messages:
            msg = gmail_service.service.users().messages().get(
                userId='me', 
                id=message['id']
            ).execute()
            
            headers = msg['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            
            body = gmail_service._extract_body(msg['payload'])
            
            emails.append({
                'id': message['id'],
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body[:500] + '...' if len(body) > 500 else body,
                'snippet': msg.get('snippet', '')
            })
        
        return json.dumps(emails, indent=2)
        
    except HttpError as e:
        logger.error(f"Gmail API error: {str(e)}")
        return json.dumps({"error": f"Gmail API error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error searching emails: {str(e)}")
        return json.dumps({"error": f"Error searching emails: {str(e)}"})

@mcp.tool()
def get_email(message_id: str) -> str:
    try:
        if not gmail_service.service:
            return json.dumps({"error": "Gmail service not authenticated"})
        
        msg = gmail_service.service.users().messages().get(
            userId='me', 
            id=message_id
        ).execute()
        
        headers = msg['payload'].get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
        to = next((h['value'] for h in headers if h['name'] == 'To'), '')
        
        body = gmail_service._extract_body(msg['payload'])
        
        email_data = {
            'id': message_id,
            'subject': subject,
            'sender': sender,
            'to': to,
            'date': date,
            'body': body,
            'snippet': msg.get('snippet', '')
        }
        
        return json.dumps(email_data, indent=2)
        
    except HttpError as e:
        logger.error(f"Gmail API error: {str(e)}")
        return json.dumps({"error": f"Gmail API error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error getting email: {str(e)}")
        return json.dumps({"error": f"Error getting email: {str(e)}"})

@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    try:
        if not gmail_service.service:
            return json.dumps({"error": "Gmail service not authenticated"})
        
        message = gmail_service._create_message(to, subject, body)
        
        sent_message = gmail_service.service.users().messages().send(
            userId='me', 
            body=message
        ).execute()
        
        result = {
            "success": True,
            "message_id": sent_message['id'],
            "message": "Email sent successfully"
        }
        
        return json.dumps(result, indent=2)
        
    except HttpError as e:
        logger.error(f"Gmail API error: {str(e)}")
        return json.dumps({"error": f"Gmail API error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return json.dumps({"error": f"Error sending email: {str(e)}"})

if __name__ == "__main__":
    mcp.run()