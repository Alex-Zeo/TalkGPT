"""
TalkGPT CLI Batch Processing Commands

Implementation of batch processing functionality for multiple files.
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from ...core.file_processor import get_file_processor
    from ...utils.config import TalkGPTConfig
    from ...utils.logger import TalkGPTLogger
    from .transcribe import transcribe_single_file
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from core.file_processor import get_file_processor
    from utils.config import TalkGPTConfig
    from utils.logger import TalkGPTLogger
    from transcribe import transcribe_single_file


def process_batch(input_dir: Path,
                 output_dir: Path,
                 config: TalkGPTConfig,
                 logger: TalkGPTLogger,
                 **options) -> Dict[str, Any]:
    """
    Process multiple files in batch.
    
    Args:
        input_dir: Input directory containing files
        output_dir: Output directory for results
        config: TalkGPT configuration
        logger: Logger instance
        **options: Override options from CLI
        
    Returns:
        Dictionary with batch processing results
    """
    start_time = time.time()
    
    # Get file processor to scan directory
    processor = get_file_processor()
    
    # Extract options
    pattern = options.get('pattern', '*')
    recursive = options.get('recursive', True)
    max_files = options.get('max_files')
    continue_on_error = options.get('continue_on_error', True)
    
    # Scan for files
    if pattern == '*':
        # Use all supported extensions
        extensions = list(processor.AUDIO_EXTENSIONS | processor.VIDEO_EXTENSIONS)
    else:
        # Use pattern as extension filter
        extensions = [f".{pattern.lstrip('*.')}" if not pattern.startswith('.') else pattern]
    
    files = processor.scan_directory(input_dir, recursive=recursive, extensions=extensions)
    
    if max_files:
        files = files[:max_files]
    
    if not files:
        return {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'total_time': 0.0,
            'files': []
        }
    
    logger.get_logger("talkgpt.batch").info(f"Starting batch processing: {len(files)} files")
    
    # Queue mode via Celery if requested
    use_queue = options.get('queue', False)
    queued_jobs = []
    if use_queue:
        try:
            from ...workers.task_manager import transcribe_file_task
            for file_path in files:
                file_output_dir = output_dir / file_path.stem
                job = transcribe_file_task.delay(
                    input_path=str(file_path),
                    output_dir=str(file_output_dir),
                    enhanced_analysis=bool(options.get('enhanced_analysis', False)),
                    formats=list(options.get('formats', []) or []),
                    language=options.get('language')
                )
                queued_jobs.append({'file': str(file_path), 'task_id': job.id})
        except Exception as e:
            logger.get_logger("talkgpt.batch").warning(f"Queue mode requested but unavailable: {e}. Falling back to inline processing.")
            use_queue = False

    # Process files inline if not queuing
    results = []
    successful = 0
    failed = 0
    
    for i, file_path in enumerate(files, 1):
        if use_queue:
            # Skip inline processing when queued
            continue
        file_output_dir = output_dir / file_path.stem
        
        logger.get_logger("talkgpt.batch").info(f"Processing {i}/{len(files)}: {file_path.name}")
        
        try:
            result = transcribe_single_file(
                input_path=file_path,
                output_dir=file_output_dir,
                config=config,
                logger=logger,
                **options
            )
            
            results.append({
                'file': str(file_path),
                'status': 'success',
                'result': result
            })
            successful += 1
            
        except Exception as e:
            error_msg = str(e)
            logger.get_logger("talkgpt.batch").error(f"Failed to process {file_path}: {error_msg}")
            
            results.append({
                'file': str(file_path),
                'status': 'failed',
                'error': error_msg
            })
            failed += 1
            
            if not continue_on_error:
                break
    
    total_time = time.time() - start_time
    
    batch_result = {
        'total': len(files),
        'successful': successful,
        'failed': failed,
        'total_time': total_time,
        'files': results,
        'queued': queued_jobs if use_queue else None
    }
    
    logger.get_logger("talkgpt.batch").info(f"Batch processing completed: {successful}/{len(files)} successful")
    
    return batch_result