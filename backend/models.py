from pydantic import BaseModel, Field
from typing import Optional, List


class SynthesizeRequest(BaseModel):
    ssml: str = Field(..., description="SSML content to synthesize")
    api_key: str = Field(..., description="Azure API key")
    region: str = Field(..., description="Azure region (e.g., eastus)")
    voice: Optional[str] = Field(None, description="Voice name (optional if in SSML)")
    output_format: str = Field(
        default="audio-16khz-32kbitrate-mono-mp3",
        description="Output audio format"
    )


class SynthesizeResponse(BaseModel):
    success: bool
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    file_size: Optional[int] = None
    error: Optional[str] = None


class VoiceInfo(BaseModel):
    name: str
    locale: str
    gender: str
    style_list: List[str] = []


class VoicesResponse(BaseModel):
    voices: List[VoiceInfo]


class ValidateRequest(BaseModel):
    ssml: str = Field(..., description="SSML content to validate")


class ValidationError(BaseModel):
    line: int
    column: int
    message: str


class ValidateResponse(BaseModel):
    valid: bool
    errors: List[ValidationError] = []
    warnings: List[str] = []