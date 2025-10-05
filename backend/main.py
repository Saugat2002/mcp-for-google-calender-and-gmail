import json
import os
import logging
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from mcp_use import MCPAgent, MCPClient
from langchain.chat_models import init_chat_model


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Session storage - in production, use Redis or database
user_sessions = {}
agents = {}  # Store agents per session

def create_session(user_data, access_token):
    """Create a new user session"""
    session_id = str(uuid.uuid4())
    user_sessions[session_id] = {
        "user_data": user_data,
        "access_token": access_token,
        "created_at": time.time(),
        "authenticated": True
    }
    return session_id

def get_session(session_id):
    """Get session data by session ID"""
    if session_id and session_id in user_sessions:
        session = user_sessions[session_id]
        # Check if session is not expired (24 hours)
        if time.time() - session["created_at"] < 86400:
            return session
        else:
            # Remove expired session
            del user_sessions[session_id]
    return None

def delete_session(session_id):
    """Delete a user session"""
    if session_id and session_id in user_sessions:
        del user_sessions[session_id]
    if session_id and session_id in agents:
        del agents[session_id]

async def authenticate_mcp_servers_for_session(session_id: str, user_email: str, token: str):
    """Authenticate MCP servers for a specific session"""
    try:
        # Create session-specific directory
        session_mcp_dir = os.path.expanduser(f"~/.config/google-calendar-mcp-{session_id}")
        os.makedirs(session_mcp_dir, exist_ok=True)
        
        credentials = {
            "installed": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "project_id": os.getenv("GOOGLE_PROJECT_ID", "enduring-amp-472702-g1"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")]
            }
        }
        
        calendar_credentials_path = os.path.join(session_mcp_dir, "gcp-oauth.keys.json")
        with open(calendar_credentials_path, 'w') as f:
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
        
        calendar_token_path = os.path.join(session_mcp_dir, "tokens.json")
        with open(calendar_token_path, 'w') as f:
            json.dump(token_data, f)
        
        logger.info(f"MCP servers authenticated for session {session_id}, user: {user_email}")
        
        # Initialize agent for this session
        agent = await initialize_agent_for_session(session_id, calendar_credentials_path, token)
        if agent:
            agents[session_id] = agent
            logger.info(f"MCP agent successfully initialized for session {session_id}")
            return True
        else:
            logger.warning(f"MCP agent initialization failed for session {session_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error authenticating MCP servers for session {session_id}: {str(e)}")
        raise

SYSTEM_PROMPT = """You are a helpful AI assistant with access to Google Calendar, Gmail, and time server. 

You can help users with:
- Calendar management (view, create, update, delete events)
- Email management (search, read, send emails)
- Time management (timezones, conversions, reminders)

NOTE: When responding to users, provide clear, concise, and direct answers. Do NOT include your internal reasoning, thought processes, or step-by-step analysis in your responses. Directly provide the final answer or result by assuming anything you are unsure about. Be conversational, helpful and user-friendly. NEVER show internal reasoning like "Let me think..." or "I need to..." in your final response."""

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
    """Initialize MCP agent for a specific session"""
    try:
        config = {
            "mcpServers": {
                "date-time-tools": {
                    "command": "npx",
                    "args": ["-y", "@abhi12299/date-time-tools"]
                },
                "google-calendar": {
                    "command": "npx",
                    "args": ["@cocal/google-calendar-mcp"],
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
        
        logger.info(f"MCP Agent initialized successfully for session {session_id}")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP Agent for session {session_id}: {str(e)}")
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # No global agent initialization needed - agents are created per session
    yield

app = FastAPI(
    title="MCP Chatbot API", 
    version="1.0.0",
    lifespan=lifespan
)

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
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                user_message = message_data.get("message", "")
                session_id = message_data.get("sessionId")
                
                if not session_id:
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": "Session ID required. Please authenticate first."
                        }), 
                        websocket
                    )
                    continue
                
                # Get agent for this session
                agent = agents.get(session_id)
                if not agent:
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": "Agent not initialized for your session. Please re-authenticate."
                        }), 
                        websocket
                    )
                    continue
                
                try:
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "typing",
                            "message": "Agent is thinking..."
                        }), 
                        websocket
                    )
                    
                    result = await agent.run(user_message)
                    
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "response",
                            "message": str(result)
                        }), 
                        websocket
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": f"Error processing your request: {str(e)}"
                        }), 
                        websocket
                    )
            
            elif message_data.get("type") == "ping":
                await manager.send_personal_message(
                    json.dumps({"type": "pong"}), 
                    websocket
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected")

@app.get("/auth/google/callback")
async def google_callback(code: str = None, state: str = None):
    try:
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not provided")
        
        logger.info(f"Received OAuth callback with code: {code[:10]}...")
        
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
            refresh_token = token_info.get('refresh_token')

            user_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = http_requests.get(user_url, headers=headers)
            
            logger.info(f"User info response status: {user_response.status_code}")
            logger.info(f"User info response: {user_response.text}")
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                user_email = user_data.get('email')
                
                if not user_email:
                    logger.info("No email in user info, trying token info")
                    user_email = f"user_{user_data.get('id', 'unknown')}@gmail.com"
                
                # Create session for this user
                session_id = create_session(user_data, access_token)
                
                # Authenticate MCP servers for this session
                await authenticate_mcp_servers_for_session(session_id, user_email, access_token)
                
                logger.info(f"Authentication successful for user: {user_email}, session: {session_id}")
                
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
                logger.warning(f"Failed to get user info: {user_response.status_code} - {user_response.text}")
                user_email = "authenticated_user@gmail.com"
                user_data = {"email": user_email, "id": "unknown", "name": "User"}
                
                # Create session for this user
                session_id = create_session(user_data, access_token)
                
                # Authenticate MCP servers for this session
                await authenticate_mcp_servers_for_session(session_id, user_email, access_token)
                
                logger.info(f"Authentication successful for user: {user_email}, session: {session_id}")
                
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
            logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=400, detail="Token exchange failed")
            
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@app.get("/auth/status")
async def get_auth_status(session_id: str = None):
    try:
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
    except Exception as e:
        logger.error(f"Error checking auth status: {str(e)}")
        return {"authenticated": False, "user": None}

@app.post("/auth/logout")
async def logout(session_id: str = None):
    try:
        if session_id:
            delete_session(session_id)
            logger.info(f"User session {session_id} logged out successfully")
        return {"success": True, "message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        return {"success": False, "message": "Logout failed"}
    
@app.get("/health")
async def health():
    """Check health of the server"""
    return {"status": "ok"}
    
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)