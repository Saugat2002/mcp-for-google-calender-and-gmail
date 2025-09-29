import React, { useState } from 'react';
import { LogIn, Loader2, Calendar, Mail, Clock, Shield, CheckCircle, Zap } from 'lucide-react';

interface GoogleSignInProps {
  onAuthSuccess: (isAuthenticated: boolean) => void;
}

const GoogleSignIn: React.FC<GoogleSignInProps> = ({ onAuthSuccess }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    
    try {
      const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '233096657076-euilsqe9aq3pi8vj41pfjsqcl6nlkker.apps.googleusercontent.com';
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
      
      const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
        `client_id=${clientId}&` +
        `redirect_uri=${backendUrl}/auth/google/callback&` +
        `scope=https://www.googleapis.com/auth/userinfo.email%20https://www.googleapis.com/auth/userinfo.profile%20https://www.googleapis.com/auth/calendar%20https://www.googleapis.com/auth/calendar.events%20https://www.googleapis.com/auth/gmail.readonly%20https://www.googleapis.com/auth/gmail.send%20https://www.googleapis.com/auth/gmail.modify&` +
        `response_type=code&` +
        `access_type=offline&` +
        `prompt=consent&` +
        `state=google_signin`;
      
      const authWindow = window.open(
        authUrl,
        'google-auth',
        'width=500,height=600,scrollbars=yes,resizable=yes'
      );

      const handleMessage = (event: MessageEvent) => {
        if (event.data === 'auth_success') {
          setIsAuthenticated(true);
          onAuthSuccess(true);
          setIsLoading(false);
          window.removeEventListener('message', handleMessage);
        }
      };

      window.addEventListener('message', handleMessage);

      const checkAuth = setInterval(async () => {
        try {
          if (authWindow?.closed) {
            clearInterval(checkAuth);
            setIsLoading(false);
            window.removeEventListener('message', handleMessage);
            
            try {
              const statusResponse = await fetch(`${backendUrl}/auth/status`);
              if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.authenticated) {
                  setIsAuthenticated(true);
                  onAuthSuccess(true);
                  setIsLoading(false);
                }
              }
            } catch (error) {
              console.error('Final auth check failed:', error);
            }
            return;
          }

          const statusResponse = await fetch(`${backendUrl}/auth/status`);
          if (statusResponse.ok) {
            const statusData = await statusResponse.json();
            
            if (statusData.authenticated) {
              clearInterval(checkAuth);
              authWindow?.close();
              setIsAuthenticated(true);
              onAuthSuccess(true);
              setIsLoading(false);
              window.removeEventListener('message', handleMessage);
            }
          }
        } catch (error) {
          console.error('Auth check failed:', error);
        }
      }, 1000);

      setTimeout(() => {
        clearInterval(checkAuth);
        window.removeEventListener('message', handleMessage);
        if (!authWindow?.closed) {
          authWindow?.close();
        }
        setIsLoading(false);
      }, 300000);

    } catch (error) {
      console.error('Google Sign-In failed:', error);
      alert(`Authentication failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsLoading(false);
    }
  };

  if (isAuthenticated) {
    return (
      <div className="auth-success">
        <div className="success-icon">
          <CheckCircle size={48} />
        </div>
        <h2>Welcome to MCP Chatbot!</h2>
        <p>Successfully authenticated with Google</p>
        <p>You can now use Calendar, Email, and Time features.</p>
        <div className="success-features">
          <div className="feature-item">
            <Calendar size={20} />
            <span>Calendar Management</span>
          </div>
          <div className="feature-item">
            <Mail size={20} />
            <span>Email Operations</span>
          </div>
          <div className="feature-item">
            <Clock size={20} />
            <span>Time & Date Tools</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="google-signin-container">
      <div className="signin-content">
        <div className="signin-header">
          <div className="app-logo">
            <Zap size={32} />
          </div>
          <h1>MCP Chatbot</h1>
          <p className="app-subtitle">AI-Powered Productivity Assistant</p>
        </div>

        <div className="features-section">
          <h3>What you can do:</h3>
          <div className="features-grid">
            <div className="feature-card">
              <Calendar className="feature-icon" />
              <h4>Calendar Management</h4>
              <p>View, create, and manage your Google Calendar events</p>
            </div>
            <div className="feature-card">
              <Mail className="feature-icon" />
              <h4>Email Operations</h4>
              <p>Read, send, and organize your Gmail messages</p>
            </div>
            <div className="feature-card">
              <Clock className="feature-icon" />
              <h4>Time & Date Tools</h4>
              <p>Get current time, timezone conversions, and date calculations</p>
            </div>
          </div>
        </div>

        <div className="security-info">
          <Shield className="security-icon" />
          <p>Your data is secure and only used to provide AI assistance</p>
        </div>

        <button
          onClick={handleGoogleSignIn}
          disabled={isLoading}
          className="google-signin-button"
        >
          {isLoading ? (
            <>
              <Loader2 className="spinner" />
              Authenticating...
            </>
          ) : (
            <>
              <LogIn size={20} />
              Sign in with Google
            </>
          )}
        </button>

        <div className="signin-footer">
          <p>By signing in, you agree to our terms of service</p>
        </div>
      </div>
    </div>
  );
};

export default GoogleSignIn;