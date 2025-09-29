import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Loader2, LogOut } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';
import GoogleSignIn from './components/GoogleSignIn';
import './App.css';

interface Message {
  id: number;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  isError?: boolean;
}

interface WebSocketMessage {
  type: 'message' | 'response' | 'typing' | 'error' | 'ping' | 'pong';
  message?: string;
}

interface UserInfo {
  id: string;
  email: string;
  name: string;
  given_name: string;
  family_name: string;
  picture: string;
  verified_email: boolean;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchUserInfo = async () => {
    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'https://mcp-chatbot-backend.onrender.com';
      const response = await fetch(`${backendUrl}/auth/status`);
      
      if (response.ok) {
        const data = await response.json();
        if (data.authenticated && data.user) {
          setUserInfo(data.user);
        }
      }
    } catch (error) {
      console.error('Failed to fetch user info:', error);
    }
  };

  const handleLogout = async () => {
    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'https://mcp-chatbot-backend.onrender.com';
      const response = await fetch(`${backendUrl}/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (response.ok) {
        setIsAuthenticated(false);
        setUserInfo(null);
        setMessages([]);
        if (ws) {
          ws.close();
          setWs(null);
        }
      }
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchUserInfo();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const connectWebSocket = () => {
      const websocket = new WebSocket('ws://localhost:8000/ws');
      
      websocket.onopen = () => {
        console.log('Connected to WebSocket');
        setWs(websocket);
      };

      websocket.onmessage = (event) => {
        const data: WebSocketMessage = JSON.parse(event.data);
        
        if (data.type === 'response') {
          setIsTyping(false);
          setMessages(prev => [...prev, {
            id: Date.now(),
            text: data.message || '',
            sender: 'bot',
            timestamp: new Date()
          }]);
        } else if (data.type === 'typing') {
          setIsTyping(true);
        } else if (data.type === 'error') {
          setIsTyping(false);
          setMessages(prev => [...prev, {
            id: Date.now(),
            text: `Error: ${data.message}`,
            sender: 'bot',
            timestamp: new Date(),
            isError: true
          }]);
        }
      };

      websocket.onclose = () => {
        console.log('WebSocket disconnected');
        setWs(null);
        setTimeout(() => {
          if (isAuthenticated) {
            console.log('Retrying WebSocket connection...');
            connectWebSocket();
          }
        }, 2000);
      };

      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      return websocket;
    };

    const websocket = connectWebSocket();

    return () => {
      if (websocket) {
        websocket.close();
      }
    };
  }, [isAuthenticated]);

  const sendMessage = () => {
    if (!inputMessage.trim() || !ws) return;

    const message: Message = {
      id: Date.now(),
      text: inputMessage,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, message]);
    setInputMessage('');

    ws.send(JSON.stringify({
      type: 'message',
      message: inputMessage.trim()
    }));
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="app">
        <div className="auth-container">
          <GoogleSignIn onAuthSuccess={setIsAuthenticated} />
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="chat-container">
        <div className="chat-header">
          <div className="header-content">
            <Bot className="bot-icon" />
            <div>
              <h1>MCP Chatbot</h1>
              <p>AI-powered calendar, email, and time assistant</p>
            </div>
          </div>
          <div className="header-right">
            {userInfo && (
              <div className="user-info">
                <img 
                  src={userInfo.picture} 
                  alt={userInfo.name}
                  className="user-avatar"
                />
                <div className="user-details">
                  <span className="user-name">{userInfo.name}</span>
                  <span className="user-email">{userInfo.email}</span>
                </div>
                <button 
                  onClick={handleLogout}
                  className="logout-button"
                  title="Logout"
                >
                  <LogOut size={16} />
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="messages-container">
          {messages.length === 0 && (
            <div className="welcome-message">
              <Bot className="welcome-icon" />
              <h2>Welcome to MCP Chatbot!</h2>
              <p>I can help you manage your Google Calendar, Gmail, and provide time information. Try asking me to:</p>
              <ul>
                <li>Show my upcoming events</li>
                <li>Create a new meeting</li>
                <li>Check my schedule for today</li>
                <li>Search my emails</li>
                <li>Send an email</li>
                <li>Read specific emails</li>
                <li>What time is it in different timezones</li>
                <li>Calculate time differences</li>
              </ul>
            </div>
          )}
          
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.sender}`}>
              <div className="message-content">
                <div className="message-avatar">
                  {message.sender === 'user' ? <User size={20} /> : <Bot size={20} />}
                </div>
                <div className="message-text">
                  {message.sender === 'bot' ? (
                    <MarkdownRenderer content={message.text} />
                  ) : (
                    <p>{message.text}</p>
                  )}
                  <span className="message-time">
                    {message.timestamp.toLocaleTimeString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
          
          {isTyping && (
            <div className="message bot">
              <div className="message-content">
                <div className="message-avatar">
                  <Bot size={20} />
                </div>
                <div className="message-text">
                  <div className="typing-indicator">
                    <Loader2 className="spinner" />
                    <span>Agent is thinking...</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <div className="input-wrapper">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message here..."
              disabled={!ws}
            />
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || !ws}
              className="send-button"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;