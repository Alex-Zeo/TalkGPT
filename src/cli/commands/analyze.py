"""
TalkGPT CLI Analysis Commands

Implementation of advanced analysis features.
"""

from pathlib import Path
from typing import Dict, Any, Optional


def analyze_speakers_command(
    input_path: Path,
    output_path: Optional[Path],
    format: str,
    config,
    logger,
) -> Dict[str, Any]:
    """Analyze speakers in audio file (pyannote optional)."""
    from ...analytics.speaker_analyzer import SpeakerAnalyzer

    analyzer = SpeakerAnalyzer(
        min_speakers=config.analytics.min_speakers,
        max_speakers=config.analytics.max_speakers,
    )

    if analyzer.pipeline is None:
        result = {
            'speaker_count': 0,
            'segments': 0,
            'overlaps': 0,
            'message': 'Speaker analyzer unavailable (pyannote not installed)'
        }
        return result

    diarization = analyzer.perform_diarization(input_path)

    summary = analyzer.get_diarization_summary(diarization)

    if output_path:
        if format == 'rttm':
            analyzer.save_diarization_result(diarization, output_path, format='rttm')
        else:
            analyzer.save_diarization_result(diarization, output_path, format='json')

    return {
        'speaker_count': summary['speaker_count'],
        'segments': summary['total_segments'],
        'overlaps': summary['total_overlaps'],
        'output': str(output_path) if output_path else None,
    }


def analyze_quality_command(
    input_path: Path,
    output_path: Optional[Path],
    threshold: float,
    config,
    logger,
) -> Dict[str, Any]:
    """Analyze transcription quality and uncertainty."""
    from ...core.chunker import get_smart_chunker
    from ...core.transcriber import get_transcriber
    from ...analytics.uncertainty_detector import UncertaintyDetector
    from ...core.resource_detector import get_device_config

    # Prepare chunking
    chunker = get_smart_chunker(
        chunk_size=config.processing.chunk_size,
        overlap_duration=config.processing.overlap_duration,
        silence_threshold=config.processing.silence_threshold,
        min_silence_len=config.processing.min_silence_len,
    )
    chunking_result = chunker.chunk_audio(input_path, remove_silence=False)

    # Prepare transcriber (auto device routing)
    device_cfg = get_device_config(
        force_device=config.transcription.device if config.transcription.device != 'auto' else None
    )
    transcriber = get_transcriber(
        model_size=config.transcription.model_size,
        device=device_cfg['device'],
        compute_type=device_cfg['compute_type'],
    )
    transcription = transcriber.transcribe_file(input_path, chunking_result, word_timestamps=config.output.word_timestamps)

    # Analyze uncertainty
    detector = UncertaintyDetector(confidence_threshold=threshold or config.analytics.confidence_threshold)
    analysis = detector.analyze_uncertainty(transcription, input_path)

    # Optional save
    if output_path:
        detector.save_uncertainty_analysis(analysis, output_path, format='json')

    return {
        'quality_score': analysis.quality_metrics.overall_quality_score,
        'flagged_segments': analysis.flagged_segments,
        'flagged_percentage': analysis.flagged_percentage,
        'output': str(output_path) if output_path else None,
    }