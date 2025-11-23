"""
Voice Activity Detection - Simplified
"""

class VoiceActivityDetector:
    """Time-based VAD (no audio decoding needed for chunks)"""
    
    def __init__(self):
        print(f"[VAD] Initialized (time-based mode)")
    
    def is_speech(self, audio_bytes: bytes) -> bool:
        """
        Simple check: if we received audio data, assume it's speech
        
        Since MediaRecorder only sends data when detecting audio,
        we can trust that any received chunk contains speech.
        """
        # Just check if chunk is large enough (> 1KB)
        is_speech = len(audio_bytes) > 1000
        
        if is_speech:
            print(f"[VAD] 🎤 Audio chunk received ({len(audio_bytes)} bytes)")
        else:
            print(f"[VAD] 🔇 Chunk too small ({len(audio_bytes)} bytes)")
        
        return is_speech