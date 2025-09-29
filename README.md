# MCP Chatbot - FastAPI + React

A modern chatbot application built with FastAPI backend and React frontend, integrated with Google Calendar through MCP (Model Context Protocol).

## Features

- 🤖 AI-powered chatbot using Google Gemini
- 📅 Google Calendar integration via MCP
- 🔄 Real-time WebSocket communication
- 💬 Modern chat interface
- 🎨 Beautiful, responsive UI
- ⚡ Fast and efficient

## Project Structure

```
mcpproject/
├── backend/                 # FastAPI backend
│   ├── main.py             # Main FastAPI application
│   ├── run.py              # Run script
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── App.css         # Styling
│   │   ├── index.js        # React entry point
│   │   └── index.css       # Global styles
│   ├── public/
│   │   └── index.html      # HTML template
│   └── package.json        # Node.js dependencies
├── gcp-oauth.keys.json     # Google OAuth credentials
├── .env                    # Environment variables
└── README.md               # This file
```

## Prerequisites

- Python 3.8+
- Node.js 16+
- Google Cloud Platform account
- Google Calendar API enabled

## Setup Instructions

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp ../.env .env
# Edit .env with your credentials

# Run the backend
python run.py
```

The backend will start on `http://localhost:8000`

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm start
```

The frontend will start on `http://localhost:3000`

### 3. Google Calendar Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials
5. Download the JSON file and place it as `gcp-oauth.keys.json`
6. Update the redirect URIs in Google Cloud Console:
   - `http://localhost:8000/oauth2callback`
   - `http://localhost:8000/auth/callback`

## Usage

1. Start both backend and frontend servers
2. Open `http://localhost:3000` in your browser
3. The chatbot will automatically connect to the backend
4. Start chatting! Try asking:
   - "Show my upcoming events"
   - "Create a meeting tomorrow at 2 PM"
   - "What's my schedule for today?"
   - "Find free time slots this week"

## API Endpoints

### WebSocket
- `ws://localhost:8000/ws` - Real-time chat communication

### REST API
- `GET /` - Health check
- `GET /health` - Detailed health status
- `POST /chat` - Send message via REST API

## Environment Variables

```env
GOOGLE_API_KEY=your_google_api_key
GOOGLE_OAUTH_CREDENTIALS=/path/to/your/oauth/credentials.json
```

## Troubleshooting

### OAuth Issues
If you encounter OAuth redirect URI mismatch errors:
1. Check your Google Cloud Console OAuth configuration
2. Ensure redirect URIs match exactly
3. Try using service account credentials instead

### Connection Issues
- Ensure both backend and frontend are running
- Check that ports 8000 and 3000 are available
- Verify WebSocket connection in browser developer tools

### MCP Agent Issues
- Check that your Google OAuth credentials are valid
- Ensure Google Calendar API is enabled
- Verify the MCP server can access your credentials file

## Development

### Backend Development
```bash
cd backend
python run.py  # Starts with auto-reload
```

### Frontend Development
```bash
cd frontend
npm start  # Starts with hot-reload
```


## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details
