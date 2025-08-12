from typing import Dict
from pydantic import BaseModel


class TranscribeAudioResponse(BaseModel):
    input_file: str
    output_directory: str
    output_files: Dict[str, str]
    processing_time: float
    processing_speed: float


