from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Dict
import os
import uuid
import tempfile
import shutil
from datetime import datetime, timedelta

from models import (
    SynthesizeRequest, SynthesizeResponse,
    VoicesResponse, VoiceInfo,
    ValidateRequest, ValidateResponse, ValidationError
)
from azure_tts import AzureTTSClient, SSMLValidator

app = FastAPI(title="SSML TTS Platform API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create temp directory for audio files
TEMP_DIR = tempfile.gettempdir()
AUDIO_DIR = os.path.join(TEMP_DIR, "tts_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Clean up old audio files periodically
def cleanup_old_files():
    """Clean up audio files older than 1 hour"""
    try:
        now = datetime.now()
        for filename in os.listdir(AUDIO_DIR):
            filepath = os.path.join(AUDIO_DIR, filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if now - file_time > timedelta(hours=1):
                    os.remove(filepath)
    except Exception as e:
        print(f"Error cleaning up files: {e}")


@app.get("/")
async def root():
    return {
        "message": "SSML TTS Platform API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/synthesize": "Synthesize speech from SSML",
            "GET /api/voices": "Get available voices",
            "POST /api/validate": "Validate SSML syntax",
            "GET /api/audio/{filename}": "Get audio file"
        }
    }


@app.post("/api/synthesize", response_model=SynthesizeResponse)
async def synthesize(request: SynthesizeRequest):
    """Synthesize speech from SSML"""
    try:
        # Clean up old files periodically
        cleanup_old_files()
        
        # Create Azure TTS client
        client = AzureTTSClient(api_key=request.api_key, region=request.region)
        
        # Synthesize audio
        audio_data, file_size, error = client.synthesize(
            ssml=request.ssml,
            output_format=request.output_format
        )
        
        if error:
            return SynthesizeResponse(
                success=False,
                error=error
            )
        
        # Save audio file
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(audio_data)
        
        # Return response
        return SynthesizeResponse(
            success=True,
            audio_url=f"/api/audio/{filename}",
            duration_ms=None,  # Duration calculation would need audio processing library
            file_size=file_size
        )
        
    except Exception as e:
        return SynthesizeResponse(
            success=False,
            error=f"Internal server error: {str(e)}"
        )


@app.get("/api/voices", response_model=VoicesResponse)
async def get_voices(region: str = "eastus", locale: str = None):
    """Get available voices from Azure TTS"""
    try:
        # Note: This endpoint needs an API key, but we'll use a default one or require it
        # For now, we'll return a mock response since we need the API key
        return VoicesResponse(
            voices=[
                VoiceInfo(
                    name="zh-CN-XiaoxiaoNeural",
                    locale="zh-CN",
                    gender="Female",
                    style_list=["general", "assistant", "chat"]
                ),
                VoiceInfo(
                    name="zh-CN-YunxiNeural",
                    locale="zh-CN",
                    gender="Male",
                    style_list=["general", "news", "narration"]
                ),
                VoiceInfo(
                    name="en-US-JennyNeural",
                    locale="en-US",
                    gender="Female",
                    style_list=["general", "calm", "cheerful"]
                ),
                VoiceInfo(
                    name="en-US-GuyNeural",
                    locale="en-US",
                    gender="Male",
                    style_list=["general", "news", "narration"]
                ),
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validate", response_model=ValidateResponse)
async def validate_ssml(request: ValidateRequest):
    """Validate SSML syntax"""
    try:
        is_valid, errors, warnings = SSMLValidator.validate(request.ssml)
        
        # Convert errors to ValidationError format
        validation_errors = []
        for error in errors:
            validation_errors.append(ValidationError(
                line=error.get("line", 1),
                column=error.get("column", 1),
                message=error.get("message", "Unknown error")
            ))
        
        return ValidateResponse(
            valid=is_valid,
            errors=validation_errors,
            warnings=warnings
        )
        
    except Exception as e:
        return ValidateResponse(
            valid=False,
            errors=[],
            warnings=[f"Validation error: {str(e)}"]
        )


@app.get("/api/audio/{filename}")
async def get_audio(filename: str, request: Request):
    """Get audio file (支持 HTTP Range,浏览器可拖动进度条 seek)"""
    filepath = os.path.join(AUDIO_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Audio file not found")

    file_size = os.path.getsize(filepath)
    range_header = request.headers.get("range")

    # 无 Range 请求 → 返回完整文件,声明支持 Range
    if not range_header:
        return FileResponse(
            filepath,
            media_type="audio/mpeg",
            headers={"Accept-Ranges": "bytes"},
        )

    # 解析 Range: bytes=start-end
    try:
        range_spec = range_header.strip().lower()
        assert range_spec.startswith("bytes=")
        start_str, _, end_str = range_spec[6:].partition("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    except Exception:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    start = max(0, start)
    end = min(end, file_size - 1)
    if start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    content_length = end - start + 1

    def iter_file():
        with open(filepath, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        iter_file(),
        status_code=206,
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Cache-Control": "no-cache",
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)