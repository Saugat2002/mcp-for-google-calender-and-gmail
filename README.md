# MCP Chatbot

A chatbot that integrates with Google Calendar and Gmail using the Model Context Protocol (MCP). Built with FastAPI and React.

## What it does

This chatbot can help you manage your Google Calendar and Gmail through natural conversation. You can ask it to:
- Show your upcoming calendar events
- Create new meetings
- Search and read your emails
- Send emails
- Get time and date information

## Tech stack

- **Backend**: FastAPI with WebSocket support
- **Frontend**: React with TypeScript
- **AI**: Google Gemini via LangChain
- **MCP**: Custom Gmail server + Google Calendar MCP
- **Auth**: Google OAuth 2.0

## Project structure

```
mcpproject/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── gmail_mcp_server.py        # Custom Gmail MCP server
│   ├── requirements.txt           # Python dependencies
│   ├── pyproject.toml            # UV project config
│   └── gcp-oauth.keys.json       # Google OAuth credentials
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Main chat interface
│   │   ├── components/
│   │   │   └── GoogleSignIn.tsx  # OAuth sign-in
│   │   ├── MarkdownRenderer.tsx  # Message formatting
│   │   └── App.css               # Styles
│   └── package.json              # Node dependencies
└── README.md
```

## Getting started

### Prerequisites

- Python 3.13+
- Node.js 18+
- UV package manager
- Google Cloud project with Calendar and Gmail APIs enabled

### Backend setup

```bash
cd backend

uv init

uv venv

source .venv/bin/activate

# Install dependencies with UV
uv sync

# Set up environment variables
# Create .env file with:
# GOOGLE_API_KEY=your_api_key
# GOOGLE_CLIENT_ID=your_client_id
# GOOGLE_CLIENT_SECRET=your_client_secret
# GOOGLE_PROJECT_ID=your_project_id
# GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Run the server
uv run main.py
```

### Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Google OAuth setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable Calendar API and Gmail API
3. Create OAuth 2.0 credentials
4. Set authorized redirect URI to `http://localhost:8000/auth/google/callback`
5. Download credentials as `gcp-oauth.keys.json` in the backend folder

## How it works

1. **Authentication**: Users sign in with Google OAuth
2. **MCP Integration**: The app connects to MCP servers for Calendar and Gmail
3. **AI Processing**: Google Gemini processes user requests
4. **Real-time Chat**: WebSocket handles the conversation flow

## Key features

- **Real-time chat** via WebSocket
- **Google Calendar integration** through MCP
- **Gmail access** with custom MCP server
- **Time and date tools** via MCP
- **Modern UI** with React and TypeScript
- **Responsive design** that works on mobile

## API endpoints

- `GET /auth/status` - Check authentication status
- `POST /auth/logout` - Sign out
- `GET /auth/google/callback` - OAuth callback
- `GET /health` - Health check
- `WebSocket /ws` - Chat communication

## Development

The backend uses UV for dependency management and the frontend uses Vite for fast development. Both support hot reloading during development.

## Environment variables

```env
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CLIENT_ID=your_oauth_client_id
GOOGLE_CLIENT_SECRET=your_oauth_client_secret
GOOGLE_PROJECT_ID=your_gcp_project_id
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```