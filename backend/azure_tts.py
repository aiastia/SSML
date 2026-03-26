import requests
import io
import re
import xml.etree.ElementTree as ET
from typing import Optional, Tuple
from models import VoiceInfo


class AzureTTSClient:
    def __init__(self, api_key: str, region: str):
        self.api_key = api_key
        self.region = region
        self.base_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    
    def _get_headers(self) -> dict:
        return {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"
        }
    
    def synthesize(self, ssml: str, output_format: str = "audio-16khz-32kbitrate-mono-mp3") -> Tuple[bytes, int, Optional[str]]:
        """
        Synthesize speech from SSML
        
        Returns:
            Tuple of (audio_data, file_size, error_message)
        """
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": output_format
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                data=ssml.encode('utf-8'),
                timeout=30
            )
            
            if response.status_code == 200:
                audio_data = response.content
                return audio_data, len(audio_data), None
            else:
                return None, 0, f"API Error: {response.status_code} - {response.text}"
                
        except requests.exceptions.Timeout:
            return None, 0, "Request timeout"
        except requests.exceptions.RequestException as e:
            return None, 0, f"Request failed: {str(e)}"
    
    def get_voices(self) -> Tuple[list, Optional[str]]:
        """
        Get available voices from Azure TTS
        
        Returns:
            Tuple of (voices_list, error_message)
        """
        try:
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                voices_data = response.json()
                voices = []
                for voice in voices_data:
                    voice_info = VoiceInfo(
                        name=voice.get("Name", ""),
                        locale=voice.get("Locale", ""),
                        gender=voice.get("Gender", ""),
                        style_list=voice.get("StyleList", [])
                    )
                    voices.append(voice_info)
                return voices, None
            else:
                return [], f"API Error: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return [], f"Request failed: {str(e)}"


class SSMLValidator:
    """SSML syntax validator"""
    
    # Allowed SSML tags
    ALLOWED_TAGS = {
        'speak', 'voice', 'prosody', 'break', 'emphasis', 
        'say-as', 'lexicon', 'p', 's', 'phoneme', 'sub', 'mstts:express-as'
    }
    
    # Dangerous attributes to check
    DANGEROUS_PATTERNS = [
        r'<!ENTITY',
        r'<!DOCTYPE',
        r'<script',
        r'javascript:',
        r'on\w+\s*='
    ]
    
    @classmethod
    def validate(cls, ssml: str) -> tuple:
        """
        Validate SSML content
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check 1: Basic dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, ssml, re.IGNORECASE):
                errors.append({
                    "line": 1,
                    "column": 1,
                    "message": f"Potentially dangerous pattern detected: {pattern}"
                })
        
        # Check 2: XML syntax
        try:
            ET.fromstring(ssml)
        except ET.ParseError as e:
            errors.append({
                "line": e.position[0] if hasattr(e, 'position') else 1,
                "column": e.position[1] if hasattr(e, 'position') else 1,
                "message": f"XML syntax error: {str(e)}"
            })
        
        # Check 3: Check for speak root element
        if not ssml.strip().lower().startswith('<speak'):
            warnings.append("SSML should start with <speak> element")
        
        # Check 4: Check for language attribute
        if 'xml:lang' not in ssml and 'lang=' not in ssml:
            warnings.append("Consider adding language attribute for better pronunciation")
        
        # Check 5: Check for voice element
        if '<voice' not in ssml:
            warnings.append("Consider adding <voice> element to specify voice")
        
        return len(errors) == 0, errors, warnings