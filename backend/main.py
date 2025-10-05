import json
import os
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from mcp_use import MCPAgent, MCPClient
from langchain.chat_models import init_chat_model

load_dotenv()

user_sessions = {}
agents = {}

def create_session(user_data, access_token):
    session_id = str(uuid.uuid4())
    user_sessions[session_id] = {
        "user_data": user_data,
        "access_token": access_token,
        "created_at": time.time(),
        "authenticated": True
    }
    return session_id

def get_session(session_id):
    if session_id and session_id in user_sessions:
        session = user_sessions[session_id]
        if time.time() - session["created_at"] < 86400:
            return session
        else:
            del user_sessions[session_id]
    return None

def delete_session(session_id):
    if session_id and session_id in user_sessions:
        del user_sessions[session_id]
    if session_id and session_id in agents:
        del agents[session_id]

async def authenticate_mcp_servers_for_session(session_id: str, user_email: str, token: str):
    session_mcp_dir = os.path.expanduser(f"~/.config/mcp-session-{session_id}")
    os.makedirs(session_mcp_dir, exist_ok=True)
    
    credentials = {
        "installed": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "project_id": os.getenv("GOOGLE_PROJECT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")]
        }
    }
    
    credentials_path = os.path.join(session_mcp_dir, "gcp-oauth.keys.json")
    with open(credentials_path, 'w') as f:
        json.dump(credentials, f)
    
    token_data = {
        "access_token": token,
        "refresh_token": None,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "scopes": [
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
        "expiry": None
    }
    
    token_path = os.path.join(session_mcp_dir, "tokens.json")
    with open(token_path, 'w') as f:
        json.dump(token_data, f)
    
    agent = await initialize_agent_for_session(session_id, credentials_path, token)
    if agent:
        agents[session_id] = agent
        return True
    return False

SYSTEM_PROMPT = """You are a helpful AI assistant with access to Calendar, Gmail, and time tools. 

You can help users with:
- Calendar management (view, create, update, delete events)
- Email management (search, read, send emails)
- Time management (timezones, conversions, reminders)

All operations use the user's timezone from their Google account settings.

IMPORTANT: Always use the appropriate tools to complete user requests. For calendar operations, use the calendar tools. For email operations, use the Gmail tools. For time operations, use the time tools.

When a user asks to add a meeting or create an event, you MUST use the create_event tool.
When a user asks to delete a meeting, you MUST use the delete_event tool.
When a user asks to list meetings, you MUST use the list_events tool.

ATTENDEES: You can add attendees to calendar events by providing their email addresses separated by commas in the attendees parameter. For example: "john@example.com, jane@example.com"

Always complete the requested action using the appropriate tools."""

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

async def initialize_agent_for_session(session_id: str, credentials_path: str, access_token: str):
    config = {
        "mcpServers": {
            "date-time-tools": {
                "command": "npx",
                "args": ["-y", "@abhi12299/date-time-tools"]
            },
            "calendar": {
                "command": "uv",
                "args": ["run", "python", "calendar_mcp_server.py"],
                "env": {
                    "GOOGLE_OAUTH_CREDENTIALS": credentials_path,
                    "GOOGLE_ACCESS_TOKEN": access_token
                }
            },
            "gmail": {
                "command": "uv",
                "args": ["run", "python", "gmail_mcp_server.py"],
                "env": {
                    "GOOGLE_OAUTH_CREDENTIALS": credentials_path,
                    "GOOGLE_ACCESS_TOKEN": access_token
                }
            }
        }
    }

    client = MCPClient.from_dict(config)
    llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    agent = MCPAgent(llm=llm, client=client, max_steps=90, system_prompt=SYSTEM_PROMPT)
    return agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="MCP Chatbot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    session_id = None
    
    while True:
        data = await websocket.receive_text()
        message_data = json.loads(data)
        
        if message_data.get("type") == "message":
            user_message = message_data.get("message", "")
            session_id = message_data.get("sessionId")
            
            if not session_id:
                await manager.send_personal_message(
                    json.dumps({"type": "error", "message": "Session ID required. Please authenticate first."}), 
                    websocket
                )
                continue
            
            agent = agents.get(session_id)
            if not agent:
                await manager.send_personal_message(
                    json.dumps({"type": "error", "message": "Agent not initialized for your session. Please re-authenticate."}), 
                    websocket
                )
                continue
            
            await manager.send_personal_message(
                json.dumps({"type": "typing", "message": "Agent is thinking..."}), 
                websocket
            )
            
            try:
                print(f"Running agent with message: {user_message}")
                result = await agent.run(user_message)
                print(f"Agent result: {str(result)}")
                await manager.send_personal_message(
                    json.dumps({"type": "response", "message": str(result)}), 
                    websocket
                )
            except Exception as e:
                print(f"Agent error: {str(e)}")
                await manager.send_personal_message(
                    json.dumps({"type": "error", "message": f"Agent error: {str(e)}"}), 
                    websocket
                )
        
        elif message_data.get("type") == "ping":
            await manager.send_personal_message(
                json.dumps({"type": "pong"}), 
                websocket
            )

@app.get("/auth/google/callback")
async def google_callback(code: str = None, state: str = None):
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    
    import requests as http_requests
    
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI")
    }
    
    response = http_requests.post(token_url, data=token_data)
    
    if response.status_code == 200:
        token_info = response.json()
        access_token = token_info.get('access_token')

        user_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = http_requests.get(user_url, headers=headers)
        
        if user_response.status_code == 200:
            user_data = user_response.json()
            user_email = user_data.get('email')
            
            if not user_email:
                user_email = f"user_{user_data.get('id', 'unknown')}@gmail.com"
            
            session_id = create_session(user_data, access_token)
            await authenticate_mcp_servers_for_session(session_id, user_email, access_token)
            
            return HTMLResponse(f"""
            <html>
                <head><title>Authentication Successful</title></head>
                <body>
                    <h1>✅ Authentication Successful!</h1>
                    <p>You can now close this window and return to the application.</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'auth_success', sessionId: '{session_id}'}}, '*');
                        }}
                        setTimeout(() => window.close(), 1000);
                    </script>
                </body>
            </html>
            """)
        else:
            user_email = "authenticated_user@gmail.com"
            user_data = {"email": user_email, "id": "unknown", "name": "User"}
            
            session_id = create_session(user_data, access_token)
            await authenticate_mcp_servers_for_session(session_id, user_email, access_token)
            
            return HTMLResponse(f"""
            <html>
                <head><title>Authentication Successful</title></head>
                <body>
                    <h1>✅ Authentication Successful!</h1>
                    <p>You can now close this window and return to the application.</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'auth_success', sessionId: '{session_id}'}}, '*');
                        }}
                        setTimeout(() => window.close(), 3000);
                    </script>
                </body>
            </html>
            """)
    else:
        raise HTTPException(status_code=400, detail="Token exchange failed")

@app.get("/auth/status")
async def get_auth_status(session_id: str = None):
    if not session_id:
        return {"authenticated": False, "user": None}
    
    session = get_session(session_id)
    if session:
        return {
            "authenticated": session["authenticated"],
            "user": session["user_data"]
        }
    else:
        return {"authenticated": False, "user": None}

@app.post("/auth/logout")
async def logout(session_id: str = None):
    if session_id:
        delete_session(session_id)
    return {"success": True, "message": "Logged out successfully"}
    
@app.get("/health")
async def health():
    return {"status": "ok"}
    
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)