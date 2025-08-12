"""
Minimal MCP-style server (HTTP MVP) exposing a transcribe tool.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Local imports
from ..utils.config import load_config
from ..cli.commands.transcribe import transcribe_single_file
from ..utils.logger import setup_logging


from .schemas.requests import TranscribeAudioRequest
from .schemas.responses import TranscribeAudioResponse


app = FastAPI(title="TalkGPT MCP Server (MVP)")


@app.post("/tools/transcribe_audio", response_model=TranscribeAudioResponse)
def transcribe_audio(req: TranscribeAudioRequest):
    input_path = Path(req.input_path)
    if not input_path.exists():
        raise HTTPException(status_code=400, detail=f"Input not found: {input_path}")

    # Load config and initialize logging for consistent logs
    cfg = load_config("default")
    setup_logging(cfg.logging)

    # Prepare options for CLI layer
    options: Dict[str, Any] = {
        'formats': req.formats,
        'enhanced_analysis': req.enhanced_analysis,
        'language': req.language,
    }
    # Remove None entries
    options = {k: v for k, v in options.items() if v is not None}

    # Use CLI implementation directly to keep one code path
    result = transcribe_single_file(
        input_path=input_path,
        output_dir=Path(req.output_dir) if req.output_dir else None,
        config=cfg,
        logger=None,  # Transcribe layer uses TalkGPTLogger internally
        **options,
    )

    return TranscribeAudioResponse(
        input_file=result['input_file'],
        output_directory=result['output_directory'],
        output_files=result['output_files'],
        processing_time=result['processing_time'],
        processing_speed=result.get('processing_speed', 0.0),
    )


