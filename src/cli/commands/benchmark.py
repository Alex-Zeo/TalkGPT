"""
TalkGPT CLI Benchmark Commands

Implementation of performance benchmarking.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List


def _find_samples(sample_dir: Optional[Path]) -> List[Path]:
    if not sample_dir or not sample_dir.exists():
        return []
    exts = {'.wav', '.mp3', '.m4a', '.flac', '.mp4', '.mkv'}
    return [p for p in sample_dir.iterdir() if p.suffix.lower() in exts]


def run_benchmark(
    duration: int,
    sample_dir: Optional[Path],
    config,
    logger,
) -> Dict[str, Any]:
    """Run a quick performance benchmark using small samples."""
    import time
    import psutil

    from ...core.file_processor import FileProcessor
    from ...core.chunker import get_smart_chunker
    from ...core.transcriber import get_transcriber
    from ...core.resource_detector import get_device_config

    samples = _find_samples(sample_dir)
    if not samples:
        return {
            'processing_speed': 0.0,
            'memory_usage': psutil.virtual_memory().percent,
            'cpu_usage': psutil.cpu_percent(interval=0.2),
            'samples': 0,
            'message': 'No sample files found'
        }

    processor = FileProcessor()
    chunker = get_smart_chunker(
        chunk_size=config.processing.chunk_size,
        overlap_duration=config.processing.overlap_duration,
        silence_threshold=config.processing.silence_threshold,
        min_silence_len=config.processing.min_silence_len,
    )

    device_cfg = get_device_config(
        force_device=config.transcription.device if config.transcription.device != 'auto' else None
    )
    transcriber = get_transcriber(
        model_size=config.transcription.model_size,
        device=device_cfg['device'],
        compute_type=device_cfg['compute_type'],
    )

    wall_start = time.time()
    total_audio = 0.0
    total_proc = 0.0
    processed = 0

    for sample in samples:
        if time.time() - wall_start > duration:
            break
        # Preprocess at conservative settings for comparability
        proc = processor.process_file(
            sample,
            Path(processor.temp_dir) / "bm",
            speed_multiplier=1.0,
            remove_silence=False,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
        )
        chunks = chunker.chunk_audio(proc.processed_path, remove_silence=False)
        if not chunks.chunks:
            continue
        # Transcribe only first chunk to bound runtime
        first_chunk = chunks.chunks[0]
        start = time.time()
        result = transcriber.transcribe_chunk(first_chunk, word_timestamps=False)
        elapsed = time.time() - start
        total_audio += first_chunk.duration
        total_proc += elapsed
        processed += 1

    mem = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent(interval=0.2)
    speed = (total_audio / total_proc) if total_proc > 0 else 0.0

    return {
        'processing_speed': round(speed, 2),
        'memory_usage': mem,
        'cpu_usage': cpu,
        'samples': processed,
    }