"""
Voice Handler - Coordinates STT → Chat Agent → TTS
"""

import sys
import os
import base64
import threading
from typing import Dict, Optional

# Add parent directory to path to import chat_agent
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'orchestrator'))

from stt_service import STTService
from tts_service import TTSService
from audio_buffer import AudioBuffer
from vad import VoiceActivityDetector

# ✅ IMPORT EXISTING CHAT AGENT
try:
    from chat_agent import run_chat_agent
    print("[VOICE_HANDLER] Successfully imported chat_agent")
except ImportError as e:
    print(f"[VOICE_HANDLER] ERROR: Cannot import chat_agent: {e}")
    print("[VOICE_HANDLER] Make sure orchestrator is in PYTHONPATH")
    raise

class VoiceSession:
    """Represents one voice conversation"""
    def __init__(self, session_id: str, conversation_id: str, user_address: str, 
                 allowed_contract: str, api_key: str):
        self.session_id = session_id
        self.conversation_id = conversation_id
        self.user_address = user_address
        self.allowed_contract = allowed_contract
        self.api_key = api_key
        
        self.audio_buffer = AudioBuffer()
        self.is_speaking = False

class VoiceHandler:
    """Manages all voice sessions"""
    
    def __init__(self):
        self.stt = STTService()
        self.tts = TTSService()
        self.vad = VoiceActivityDetector()
        
        self.sessions: Dict[str, VoiceSession] = {}
        
        print("[VOICE_HANDLER] Initialized")
    
    def start_session(self, session_id: str, conversation_id: str, 
                     user_address: str, allowed_contract: str, api_key: str):
        """Start a new voice session"""
        self.sessions[session_id] = VoiceSession(
            session_id=session_id,
            conversation_id=conversation_id,
            user_address=user_address,
            allowed_contract=allowed_contract,
            api_key=api_key
        )
        print(f"[VOICE_HANDLER] Session started: {session_id}")
    
    def process_audio_chunk(self, session_id: str, audio_base64: str, 
                           audio_format: str) -> Optional[dict]:
        """
        Process incoming audio chunk
        
        Strategy: ONLY accumulate - processing happens on manual stop
        """
        if session_id not in self.sessions:
            return {"type": "error", "message": "Session not found"}
        
        session = self.sessions[session_id]
        
        # Decode audio chunk
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as e:
            print(f"[VOICE_HANDLER] Error decoding audio: {e}")
            return {"type": "error", "message": "Invalid audio data"}
        
        # ✅ SIMPLIFIED: Just accumulate, no timers
        session.audio_buffer.add_chunk(audio_bytes)
        session.is_speaking = True
        
        # Show progress
        total_bytes = len(session.audio_buffer.get_complete_audio())
        duration = session.audio_buffer.get_duration_estimate()
        print(f"[VOICE_HANDLER] 🎤 Buffering: {total_bytes} bytes (~{duration:.1f}s)")
        
        # Return immediately
        return {"type": "listening", "message": f"Recording: {duration:.1f}s"}
    
    def finalize_audio(self, session_id: str):
        """
        User pressed stop - process the complete audio
        """
        if session_id not in self.sessions:
            return {"type": "error", "message": "Session not found"}
        
        session = self.sessions[session_id]
        
        # Get complete audio
        complete_audio = session.audio_buffer.get_complete_audio()
        
        # Check minimum duration
        MIN_AUDIO_BYTES = 10000  # ~0.3 seconds
        
        if not complete_audio or len(complete_audio) < MIN_AUDIO_BYTES:
            print(f"[VOICE_HANDLER] Audio too short ({len(complete_audio)} bytes), ignoring")
            session.audio_buffer.clear()
            session.is_speaking = False
            return {"type": "error", "message": "Audio too short - please speak longer"}
        
        print(f"[VOICE_HANDLER] ✅ Processing utterance ({len(complete_audio)} bytes)")
        
        try:
            # 1. Speech-to-Text
            print("[VOICE_HANDLER] → Starting STT...")
            text = self.stt.transcribe(complete_audio)
            
            if not text or text.strip() == "":
                print("[VOICE_HANDLER] No speech detected in transcription")
                session.audio_buffer.clear()
                session.is_speaking = False
                return {"type": "error", "message": "No speech detected"}
            
            print(f"[VOICE_HANDLER] ✅ Transcribed: '{text}'")
            
            # 2. Send to chat agent
            print("[VOICE_HANDLER] → Calling chat agent...")
            result = run_chat_agent(
                message=text,
                user_address=session.user_address,
                conversation_id=session.conversation_id,
                allowed_contract=session.allowed_contract
            )
            
            print(f"[VOICE_HANDLER] ✅ Chat agent response type: {result['type']}")
            
            # 3. Generate response
            if result["type"] == "text":
                response_text = result["message"]
                
                # Text-to-Speech
                print("[VOICE_HANDLER] → Starting TTS...")
                audio_response = self.tts.synthesize(response_text)
                
                response_data = {
                    "type": "voice_response",
                    "text": response_text,
                    "audio": base64.b64encode(audio_response).decode('utf-8'),
                    "format": "mp3"
                }
                
                print(f"[VOICE_HANDLER] ✅ Generated audio response: {len(audio_response)} bytes")
                
            elif result["type"] == "transaction":
                response_data = {
                    "type": "transaction",
                    "message": result["message"],
                    "transaction": result["transaction"]
                }
            
            else:
                response_data = {
                    "type": "error",
                    "message": result.get("message", "Unknown error")
                }
            
        except Exception as e:
            print(f"[VOICE_HANDLER] ❌ Error processing utterance: {e}")
            import traceback
            traceback.print_exc()
            response_data = {
                "type": "error",
                "message": f"Processing error: {str(e)}"
            }
        
        # Reset session state
        session.audio_buffer.clear()
        session.is_speaking = False
        
        # Return response to be emitted by main.py
        return response_data
    
    def cleanup_session(self, session_id: str):
        """Clean up when user disconnects"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"[VOICE_HANDLER] Session cleaned up: {session_id}")