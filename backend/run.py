#!/usr/bin/env python3

import uvicorn
import os
from dotenv import load_dotenv

os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = ""
os.environ["GRPC_VERBOSITY"] = "ERROR"

load_dotenv()

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY not found in environment variables")
        print("Please set GOOGLE_API_KEY in your .env file or environment")
    
    if not os.getenv("GOOGLE_OAUTH_CREDENTIALS"):
        print("Warning: GOOGLE_OAUTH_CREDENTIALS not found in environment variables")
        print("Please set GOOGLE_OAUTH_CREDENTIALS in your .env file or environment")
    
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )