import json
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from mcp_use import MCPAgent, MCPClient
from langchain.chat_models import init_chat_model


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

agent = None
auth_status = False
user_info = None
AUTH_STATUS_FILE = "auth_status.json"
USER_INFO_FILE = "user_info.json"

def save_auth_status(status: bool):
    try:
        with open(AUTH_STATUS_FILE, 'w') as f:
            json.dump({"authenticated": status}, f)
    except Exception as e:
        logger.error(f"Error saving auth status: {str(e)}")

def load_auth_status():
    global auth_status
    try:
        if os.path.exists(AUTH_STATUS_FILE):
            with open(AUTH_STATUS_FILE, 'r') as f:
                data = json.load(f)
                auth_status = data.get("authenticated", False)
    except Exception as e:
        logger.error(f"Error loading auth status: {str(e)}")

def save_user_info(user_data):
    try:
        with open(USER_INFO_FILE, 'w') as f:
            json.dump(user_data, f)
    except Exception as e:
        logger.error(f"Error saving user info: {str(e)}")

def load_user_info():
    global user_info
    try:
        if os.path.exists(USER_INFO_FILE):
            with open(USER_INFO_FILE, 'r') as f:
                user_info = json.load(f)
    except Exception as e:
        logger.error(f"Error loading user info: {str(e)}")

async def authenticate_mcp_servers(user_email: str, token: str):
    try:
        calendar_mcp_dir = os.path.expanduser("~/.config/google-calendar-mcp")
        os.makedirs(calendar_mcp_dir, exist_ok=True)
        
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
        
        calendar_credentials_path = os.path.join(calendar_mcp_dir, "gcp-oauth.keys.json")
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
                "https://www.googleapis.com/auth/calender.events",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.modify",
            ],
            "expiry": None
        }
        
        calendar_token_path = os.path.join(calendar_mcp_dir, "tokens.json")
        with open(calendar_token_path, 'w') as f:
            json.dump(token_data, f)
        
        os.environ["GOOGLE_OAUTH_CREDENTIALS"] = calendar_credentials_path
        os.environ["GOOGLE_ACCESS_TOKEN"] = token
        
        logger.info(f"MCP servers authenticated for user: {user_email}")
        
        reinit_success = await reinitialize_agent()
        if reinit_success:
            logger.info(f"MCP agent successfully reinitialized for user: {user_email}")
        else:
            logger.warning(f"MCP agent reinitialization failed for user: {user_email}")
        
    except Exception as e:
        logger.error(f"Error authenticating MCP servers: {str(e)}")
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

async def initialize_agent():
    global agent
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
                        "GOOGLE_OAUTH_CREDENTIALS": os.getenv("GOOGLE_OAUTH_CREDENTIALS", "/Users/saugatadhikari/Saugat/WORK/IBRIZ/AssesmentTask/mcpproject/backend/gcp-oauth.keys.json"),
                        "GOOGLE_ACCESS_TOKEN": os.getenv("GOOGLE_ACCESS_TOKEN", "")
                    }
                },
                "gmail": {
                    "command": "uv",
                    "args": ["run", "python", "gmail_mcp_server.py"],
                    "env": {
                        "GOOGLE_OAUTH_CREDENTIALS": os.getenv("GOOGLE_OAUTH_CREDENTIALS", "/Users/saugatadhikari/Saugat/WORK/IBRIZ/AssesmentTask/mcpproject/backend/gcp-oauth.keys.json"),
                        "GOOGLE_ACCESS_TOKEN": os.getenv("GOOGLE_ACCESS_TOKEN", "")
                    }
                }
            }
        }

        client = MCPClient.from_dict(config)
        llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
        agent = MCPAgent(llm=llm, client=client, max_steps=90, system_prompt=SYSTEM_PROMPT)
        
        logger.info("MCP Agent initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP Agent: {str(e)}")
        return False

async def reinitialize_agent():
    global agent
    try:
        if agent:
            try:
                if hasattr(agent, 'client') and hasattr(agent.client, 'close'):
                    await agent.client.close()
            except Exception as e:
                logger.warning(f"Error closing existing agent: {str(e)}")
        
        success = await initialize_agent()
        if success:
            logger.info("MCP Agent reinitialized successfully with new credentials")
        else:
            logger.error("Failed to reinitialize MCP Agent")
        return success
        
    except Exception as e:
        logger.error(f"Error reinitializing MCP Agent: {str(e)}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_agent()
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
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                user_message = message_data.get("message", "")
                
                if not agent:
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": "Agent not initialized. Please check server logs."
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
    global auth_status
    
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
            "redirect_uri": "http://localhost:8000/auth/google/callback"
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
                
                os.environ["GOOGLE_ACCESS_TOKEN"] = access_token
                await authenticate_mcp_servers(user_email, access_token)
                
                auth_status = True
                user_info = user_data
                
                save_auth_status(True)
                save_user_info(user_data)
                
                logger.info(f"Authentication successful for user: {user_email}")
                logger.info(f"Stored user_info: {user_info}")
                
                return """
                <html>
                    <head><title>Authentication Successful</title></head>
                    <body>
                        <h1>✅ Authentication Successful!</h1>
                        <p>You can now close this window and return to the application.</p>
                        <script>
                            if (window.opener) {
                                window.opener.postMessage('auth_success', '*');
                            }
                            setTimeout(() => window.close(), 3000);
                        </script>
                    </body>
                </html>
                """
            else:
                logger.warning(f"Failed to get user info: {user_response.status_code} - {user_response.text}")
                user_email = "authenticated_user@gmail.com"
                
                await authenticate_mcp_servers(user_email, access_token)
                
                auth_status = True
                
                logger.info(f"Authentication successful for user: {user_email}")
                
                return """
                <html>
                    <head><title>Authentication Successful</title></head>
                    <body>
                        <h1>✅ Authentication Successful!</h1>
                        <p>You can now close this window and return to the application.</p>
                        <script>
                            if (window.opener) {
                                window.opener.postMessage('auth_success', '*');
                            }
                            setTimeout(() => window.close(), 3000);
                        </script>
                    </body>
                </html>
                """
        else:
            logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=400, detail="Token exchange failed")
            
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@app.get("/auth/status")
async def get_auth_status():
    global auth_status, user_info
    try:
        load_auth_status()
        load_user_info()
        
        logger.info(f"Auth status check - authenticated: {auth_status}, user_info: {user_info}")
        logger.info(f"USER_INFO_FILE exists: {os.path.exists(USER_INFO_FILE)}")
        if os.path.exists(USER_INFO_FILE):
            with open(USER_INFO_FILE, 'r') as f:
                file_content = f.read()
                logger.info(f"USER_INFO_FILE content: {file_content}")
        
        return {
            "authenticated": auth_status,
            "user": user_info if auth_status else None
        }
    except Exception as e:
        logger.error(f"Error checking auth status: {str(e)}")
        return {"authenticated": False, "user": None}

@app.post("/auth/logout")
async def logout():
    global auth_status, user_info
    try:
        auth_status = False
        user_info = None
        
        save_auth_status(False)
        if os.path.exists(USER_INFO_FILE):
            os.remove(USER_INFO_FILE)
        
        logger.info("User logged out successfully")
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