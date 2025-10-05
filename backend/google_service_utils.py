#!/usr/bin/env python3

import json
import os
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import pytz

class GoogleServiceBase:
    def __init__(self, service_name: str, api_version: str, scopes: list):
        self.service_name = service_name
        self.api_version = api_version
        self.scopes = scopes
        self.service = None
        self.credentials = None
        self.user_timezone = None
    
    def authenticate_with_token_data(self, credentials_path: str, token_data: dict):
        with open(credentials_path, 'r') as f:
            json.load(f)
        
        self.credentials = Credentials(
            token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes', self.scopes)
        )
        
        self.service = build(self.service_name, self.api_version, credentials=self.credentials)
        self._get_user_timezone()
        return True
    
    def _get_user_timezone(self):
        manual_tz = os.getenv('USER_TIMEZONE')
        self.user_timezone = pytz.timezone(manual_tz) if manual_tz else pytz.timezone('Asia/Kathmandu')
    
    def get_user_timezone(self):
        return self.user_timezone or pytz.timezone('Asia/Kathmandu')
    
    def get_current_user_time(self):
        return datetime.now(self.get_user_timezone())

def initialize_google_service(service_class, service_name: str, default_scopes: list):
    credentials_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS", "/Users/saugatadhikari/Saugat/WORK/IBRIZ/AssesmentTask/mcpproject/backend/gcp-oauth.keys.json")
    token_string = os.getenv("GOOGLE_ACCESS_TOKEN", "")
    
    if not token_string or not os.path.exists(credentials_path):
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
            "scopes": default_scopes
        }
    
    return service_class.authenticate_with_token_data(credentials_path, token_data)

def get_timezone_info(service_instance):
    current_time = service_instance.get_current_user_time()
    return json.dumps({
        "timezone": str(service_instance.get_user_timezone()),
        "current_time": current_time.isoformat(),
        "utc_offset": current_time.strftime("%z")
    })

def parse_datetime_string(dt_string: str, user_timezone):
    if not dt_string:
        return None
    
    if dt_string.endswith('Z') or '+' in dt_string:
        dt = datetime.fromisoformat(dt_string[:-1] if dt_string.endswith('Z') else dt_string)
        if dt_string.endswith('Z'):
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(user_timezone).isoformat()
    
    for fmt in ['%Y-%m-%d %I:%M:%S %p', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
        try:
            return user_timezone.localize(datetime.strptime(dt_string, fmt)).isoformat()
        except ValueError:
            continue
    
    return user_timezone.localize(datetime.fromisoformat(dt_string)).isoformat()

def convert_date_to_user_timezone(date_string: str, user_timezone):
    if not date_string or date_string == 'Unknown Date':
        return date_string
    
    from email.utils import parsedate_to_datetime
    dt = parsedate_to_datetime(date_string)
    return dt.astimezone(user_timezone).strftime("%a, %d %b %Y %H:%M:%S %z")