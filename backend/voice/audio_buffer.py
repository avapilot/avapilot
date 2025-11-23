"""
Audio Buffer - Accumulates audio chunks
"""

class AudioBuffer:
    """Buffers audio chunks until utterance is complete"""
    
    def __init__(self):
        self.chunks = []
    
    def add_chunk(self, audio_bytes: bytes):
        """Add audio chunk to buffer"""
        self.chunks.append(audio_bytes)
    
    def get_complete_audio(self) -> bytes:
        """Get all buffered audio as single byte string"""
        return b''.join(self.chunks)
    
    def clear(self):
        """Clear buffer"""
        self.chunks = []
    
    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        return len(self.chunks) == 0
    
    def get_duration_estimate(self) -> float:
        """Rough estimate of audio duration in seconds (assuming 16kHz)"""
        total_bytes = sum(len(chunk) for chunk in self.chunks)
        # Rough estimate: 16kHz * 2 bytes/sample = 32000 bytes/second
        return total_bytes / 32000 if total_bytes > 0 else 0