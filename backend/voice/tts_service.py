"""
Text-to-Speech Service
"""

from google.cloud import texttospeech
import os

class TTSService:
    """Text-to-Speech handler"""
    
    def __init__(self, provider: str = "google"):
        self.provider = provider
        
        if provider == "google":
            self.client = texttospeech.TextToSpeechClient()
            self.voice_id = os.getenv("TTS_VOICE", "en-US-Journey-D")
        
        print(f"[TTS] Initialized with provider: {provider}")
    
    def synthesize(self, text: str) -> bytes:
        """
        Convert text to audio
        
        Args:
            text: Text to synthesize
            
        Returns:
            MP3 audio bytes
        """
        # Limit text length
        if len(text) > 5000:
            text = text[:5000] + "..."
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=self.voice_id,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0
        )
        
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        print(f"[TTS] Generated audio: {len(response.audio_content)} bytes")
        
        return response.audio_content