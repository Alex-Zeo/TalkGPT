"""
Celery tasks for TalkGPT.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from .celery_app import celery_app


@celery_app.task(name="talkgpt.transcribe_file")
def transcribe_file_task(
    input_path: str,
    output_dir: Optional[str] = None,
    enhanced_analysis: bool = False,
    formats: Optional[list] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    from ..utils.config import load_config
    from ..cli.commands.transcribe import transcribe_single_file

    cfg = load_config("default")
    options = {
        'formats': formats,
        'enhanced_analysis': enhanced_analysis,
        'language': language,
    }
    options = {k: v for k, v in options.items() if v is not None}

    result = transcribe_single_file(
        input_path=Path(input_path),
        output_dir=Path(output_dir) if output_dir else None,
        config=cfg,
        logger=None,
        **options,
    )
    return result


