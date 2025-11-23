"""
Speech-to-Text Service
"""

import os
import io
from google.cloud import speech_v1 as speech
from pydub import AudioSegment
import tempfile

class STTService:
    """Speech-to-Text handler"""
    
    def __init__(self, provider: str = "google"):
        self.provider = provider
        
        if provider == "google":
            self.client = speech.SpeechClient()
        
        print(f"[STT] Initialized with provider: {provider}")
    
    def transcribe(self, audio_bytes: bytes, audio_format: str = "webm") -> str:
        """
        Transcribe audio to text
        """
        print(f"[STT] Transcribing {len(audio_bytes)} bytes of {audio_format}")
        
        # Convert to WAV if needed
        if audio_format != "wav":
            try:
                audio_bytes = self._convert_to_wav(audio_bytes, audio_format)
                print(f"[STT] Converted to WAV: {len(audio_bytes)} bytes")
            except Exception as e:
                print(f"[STT] ❌ Conversion failed: {e}")
                raise
        
        if self.provider == "google":
            return self._google_stt(audio_bytes)
        else:
            raise ValueError(f"Unknown STT provider: {self.provider}")
    
    def _convert_to_wav(self, audio_bytes: bytes, source_format: str) -> bytes:
        """
        Convert audio to 16kHz mono 16-bit WAV
        
        Uses temporary file to avoid pydub chunk issues
        """
        try:
            # Write to temp file first (more reliable for WebM)
            with tempfile.NamedTemporaryFile(suffix=f'.{source_format}', delete=False) as temp_input:
                temp_input.write(audio_bytes)
                temp_input_path = temp_input.name
            
            # Load from file (works better than BytesIO for WebM)
            audio = AudioSegment.from_file(temp_input_path, format=source_format)
            
            # Clean up temp file
            os.unlink(temp_input_path)
            
            # Convert to 16kHz mono 16-bit
            audio = (audio
                    .set_frame_rate(16000)
                    .set_channels(1)
                    .set_sample_width(2))  # 2 bytes = 16 bits
            
            # Export to WAV
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            
            wav_bytes = wav_buffer.getvalue()
            
            # Verify WAV header
            if len(wav_bytes) > 44:  # WAV header is 44 bytes
                sample_width_byte = wav_bytes[34:36]  # Bytes 34-35 contain bit depth
                bit_depth = int.from_bytes(sample_width_byte, 'little')
                print(f"[STT] ✅ Conversion successful (bit depth: {bit_depth}-bit)")
                
                if bit_depth != 16:
                    raise ValueError(f"Expected 16-bit audio, got {bit_depth}-bit")
            
            return wav_bytes
            
        except Exception as e:
            print(f"[STT] ❌ Conversion error: {e}")
            raise
    
    def _google_stt(self, audio_bytes: bytes) -> str:
        """Google Cloud Speech-to-Text"""
        audio = speech.RecognitionAudio(content=audio_bytes)
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True
        )
        
        response = self.client.recognize(config=config, audio=audio)
        
        if not response.results:
            print("[STT] No transcription results")
            return ""
        
        transcript = response.results[0].alternatives[0].transcript
        print(f"[STT] ✅ Transcribed: '{transcript}'")
        return transcript