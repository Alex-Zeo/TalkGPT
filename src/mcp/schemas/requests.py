from typing import List, Optional
from pydantic import BaseModel, Field


class TranscribeAudioRequest(BaseModel):
    input_path: str = Field(..., description="Path to audio/video file")
    output_dir: Optional[str] = Field(None, description="Output directory")
    formats: Optional[List[str]] = Field(None, description="Requested output formats")
    enhanced_analysis: Optional[bool] = Field(False, description="Enable enhanced analysis")
    language: Optional[str] = Field(None, description="Force language code")


