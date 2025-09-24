#!/usr/bin/env python3
"""
Render.com startup script for Chess Multiplayer Server
Production-ready entry point using minimal server
"""
import os

if __name__ == '__main__':
    # Get port from environment (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    print(f"Starting Chess Server on port {port}")
    
    # Import and run the minimal server
    from chess_server_render import app, socketio
    
    # Run with production settings
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,  # Always False in production
        allow_unsafe_werkzeug=True  # Required for production deployment
    )