"""
Real-time Voice Service
WebSocket-based voice conversation handler
"""

from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os

from voice_handler import VoiceHandler

# Initialize Flask + SocketIO
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Voice handler (manages conversations)
voice_handler = VoiceHandler()

# ✅ ADD: Serve voice widget files
WIDGET_DIR = os.path.join(os.path.dirname(__file__), '../../frontend/widget')

@app.route('/health')
def health():
    """Health check"""
    return {"status": "healthy", "service": "avapilot-voice"}

@app.route('/widget-voice.js')
def serve_voice_widget_js():
    """Serve the voice widget loader"""
    try:
        return send_from_directory(WIDGET_DIR, 'widget-voice.js', mimetype='application/javascript')
    except FileNotFoundError:
        return {"error": "widget-voice.js not found"}, 404

@app.route('/widget-voice.html')
def serve_voice_widget_html():
    """Serve the voice chat interface"""
    try:
        return send_from_directory(WIDGET_DIR, 'widget-voice.html')
    except FileNotFoundError:
        return {"error": "widget-voice.html not found"}, 404

@app.route('/debug')
def debug():
    """Debug endpoint to check active sessions"""
    sessions_info = []
    for session_id, session in voice_handler.sessions.items():
        sessions_info.append({
            "session_id": session_id,
            "conversation_id": session.conversation_id,
            "is_speaking": session.is_speaking,
            "buffer_size": len(session.audio_buffer.get_complete_audio()),
            "has_timer": session.silence_timer is not None
        })
    
    return {
        "status": "healthy",
        "active_sessions": len(voice_handler.sessions),
        "sessions": sessions_info,
        "vad_threshold": voice_handler.vad.energy_threshold
    }

@socketio.on('connect')
def handle_connect():
    """Client connected to voice channel"""
    print(f"[VOICE] Client connected: {request.sid}")
    emit('voice_ready', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    print(f"[VOICE] Client disconnected: {request.sid}")
    voice_handler.cleanup_session(request.sid)

@socketio.on('start_conversation')
def handle_start(data):
    """Start a new voice conversation"""
    session_id = request.sid
    conversation_id = data.get('conversation_id')
    user_address = data.get('user_address')
    allowed_contract = data.get('allowed_contract')
    api_key = data.get('api_key')
    
    print(f"[VOICE] Starting conversation: {conversation_id}")
    
    voice_handler.start_session(
        session_id=session_id,
        conversation_id=conversation_id,
        user_address=user_address,
        allowed_contract=allowed_contract,
        api_key=api_key
    )
    
    emit('conversation_started', {'conversation_id': conversation_id})

@socketio.on('audio_chunk')
def handle_audio(data):
    """
    Receive audio chunk from client
    
    Expected data:
    {
        "audio": base64-encoded audio bytes,
        "format": "webm" | "wav",
        "sample_rate": 16000
    }
    """
    session_id = request.sid
    audio_base64 = data.get('audio')
    audio_format = data.get('format', 'webm')
    
    # Process audio chunk
    result = voice_handler.process_audio_chunk(
        session_id=session_id,
        audio_base64=audio_base64,
        audio_format=audio_format
    )
    
    # Send back to client
    if result:
        emit('voice_response', result)

@socketio.on('stop_speaking')
def handle_stop():
    """User manually stopped speaking"""
    session_id = request.sid
    result = voice_handler.finalize_audio(session_id)
    
    if result:
        emit('voice_response', result)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8081))
    print(f"[VOICE] Starting server on port {port}")
    print(f"[VOICE] Voice widget: http://localhost:{port}/widget-voice.js")
    socketio.run(app, host='0.0.0.0', port=port, debug=True)