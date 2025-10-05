#!/usr/bin/env python3

import json
from datetime import timedelta
from fastmcp import FastMCP
from google_service_utils import GoogleServiceBase, initialize_google_service, get_timezone_info, parse_datetime_string
import pytz

mcp = FastMCP("calendar-mcp-server")

class CalendarService(GoogleServiceBase):
    def __init__(self):
        super().__init__('calendar', 'v3', [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events"
        ])
    
    def _get_user_timezone(self):
        import os
        manual_tz = os.getenv('USER_TIMEZONE')
        if manual_tz:
            self.user_timezone = pytz.timezone(manual_tz)
            return
        try:
            calendar = self.service.calendarList().list().execute()
            for cal in calendar.get('items', []):
                if cal.get('primary'):
                    details = self.service.calendars().get(calendarId=cal['id']).execute()
                    tz = details.get('timeZone')
                    if tz:
                        self.user_timezone = pytz.timezone(tz)
                        return
        except:
            pass
        self.user_timezone = pytz.timezone('Asia/Kathmandu')

calendar_service = CalendarService()
initialize_google_service(calendar_service, "Calendar", calendar_service.scopes)

@mcp.tool()
def get_calendar_timezone_info():
    return get_timezone_info(calendar_service)

@mcp.tool()
def list_events(max_results: int = 10, time_min: str = None, time_max: str = None):
    if not time_min:
        time_min = calendar_service.get_current_user_time().isoformat()
    if not time_max:
        time_max = (calendar_service.get_current_user_time() + timedelta(days=30)).isoformat()
    
    if time_min:
        time_min = parse_datetime_string(time_min, calendar_service.get_user_timezone())
    if time_max:
        time_max = parse_datetime_string(time_max, calendar_service.get_user_timezone())
    
    events_result = calendar_service.service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    event_list = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        event_list.append({
            'id': event['id'],
            'summary': event.get('summary', 'No Title'),
            'start': start,
            'end': end,
            'description': event.get('description', ''),
            'location': event.get('location', ''),
            'status': event.get('status', '')
        })
    return json.dumps(event_list, indent=2)

@mcp.tool()
def create_event(summary: str, start_time: str, end_time: str, description: str = "", location: str = ""):
    start_time_parsed = parse_datetime_string(start_time, calendar_service.get_user_timezone())
    end_time_parsed = parse_datetime_string(end_time, calendar_service.get_user_timezone())
    
    user_tz = calendar_service.get_user_timezone()
    timezone_str = str(user_tz)
    
    event = {
        'summary': summary,
        'description': description,
        'location': location,
        'start': {'dateTime': start_time_parsed, 'timeZone': timezone_str},
        'end': {'dateTime': end_time_parsed, 'timeZone': timezone_str}
    }
    
    created_event = calendar_service.service.events().insert(calendarId='primary', body=event).execute()
    return json.dumps({
        "success": True,
        "event_id": created_event['id'],
        "event_link": created_event.get('htmlLink', ''),
        "message": "Event created successfully"
    }, indent=2)

@mcp.tool()
def get_event(event_id: str):
    event = calendar_service.service.events().get(calendarId='primary', eventId=event_id).execute()
    return json.dumps({
        'id': event['id'],
        'summary': event.get('summary', 'No Title'),
        'start': event['start'].get('dateTime', event['start'].get('date')),
        'end': event['end'].get('dateTime', event['end'].get('date')),
        'description': event.get('description', ''),
        'location': event.get('location', ''),
        'status': event.get('status', ''),
        'html_link': event.get('htmlLink', '')
    }, indent=2)

@mcp.tool()
def update_event(event_id: str, summary: str = None, start_time: str = None, end_time: str = None, description: str = None, location: str = None):
    event = calendar_service.service.events().get(calendarId='primary', eventId=event_id).execute()
    
    if summary:
        event['summary'] = summary
    
    user_tz = calendar_service.get_user_timezone()
    timezone_str = str(user_tz)
    
    if start_time:
        start_time_parsed = parse_datetime_string(start_time, calendar_service.get_user_timezone())
        event['start'] = {'dateTime': start_time_parsed, 'timeZone': timezone_str}
    if end_time:
        end_time_parsed = parse_datetime_string(end_time, calendar_service.get_user_timezone())
        event['end'] = {'dateTime': end_time_parsed, 'timeZone': timezone_str}
    if description is not None:
        event['description'] = description
    if location is not None:
        event['location'] = location
    
    updated_event = calendar_service.service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
    return json.dumps({
        "success": True,
        "event_id": updated_event['id'],
        "message": "Event updated successfully"
    }, indent=2)

@mcp.tool()
def delete_event(event_id: str):
    calendar_service.service.events().delete(calendarId='primary', eventId=event_id).execute()
    return json.dumps({
        "success": True,
        "message": "Event deleted successfully"
    }, indent=2)

if __name__ == "__main__":
    mcp.run()