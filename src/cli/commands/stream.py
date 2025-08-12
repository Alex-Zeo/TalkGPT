"""
Streaming transcription (MVP) - optional dependency on sounddevice.
"""

from pathlib import Path
from typing import Optional
import time
import tempfile


def stream_transcription(
    duration: int,
    device: Optional[int],
    language: Optional[str],
    chunk_seconds: float,
    overlap_seconds: float,
    config,
    logger,
) -> bool:
    try:
        import sounddevice as sd
        import soundfile as sf
    except Exception:
        print("Streaming requires 'sounddevice' (optional). Please install: pip install sounddevice")
        return False

    samplerate = 16000
    channels = 1
    if device is not None:
        sd.default.device = device

    from ...core.transcriber import get_transcriber
    from ...core.chunker import SmartChunker, AudioChunk, ChunkingResult
    from ...core.resource_detector import get_device_config

    device_cfg = get_device_config(
        force_device=config.transcription.device if config.transcription.device != 'auto' else None
    )
    transcriber = get_transcriber(
        model_size=config.transcription.model_size,
        device=device_cfg['device'],
        compute_type=device_cfg['compute_type'],
    )

    print("🎤 Streaming... Press Ctrl+C to stop.")
    start_time = time.time()
    last_end = 0.0
    temp_dir = Path(tempfile.gettempdir()) / "talkgpt_stream"
    temp_dir.mkdir(exist_ok=True)

    try:
        with sd.InputStream(samplerate=samplerate, channels=channels):
            while time.time() - start_time < duration:
                frames = int(chunk_seconds * samplerate)
                audio = sd.rec(frames, samplerate=samplerate, channels=channels, dtype='float32')
                sd.wait()
                # Save chunk to wav
                wav_path = temp_dir / f"chunk_{int(last_end)}.wav"
                sf.write(str(wav_path), audio, samplerate)

                # Create a synthetic AudioChunk and result wrapper for transcribe_chunk
                chunk = AudioChunk(
                    chunk_id=int(last_end),
                    start_time=last_end - overlap_seconds if last_end > 0 else 0.0,
                    end_time=last_end + chunk_seconds,
                    duration=chunk_seconds + (overlap_seconds if last_end > 0 else 0.0),
                    file_path=wav_path,
                    original_start=last_end,
                    original_end=last_end + chunk_seconds,
                    overlap_prev=overlap_seconds if last_end > 0 else 0.0,
                    overlap_next=0.0,
                )

                result = transcriber.transcribe_chunk(
                    chunk,
                    language=language,
                    temperature=config.transcription.temperature,
                    beam_size=config.transcription.beam_size,
                    word_timestamps=False,
                )
                # Print incremental result
                text = result.text.strip()
                if text:
                    ts = time.strftime('%H:%M:%S', time.gmtime(last_end))
                    print(f"[{ts}] {text}")

                last_end += chunk_seconds
        return True
    except KeyboardInterrupt:
        print("\n⏹️  Stopped streaming.")
        return True
    except Exception as e:
        print(f"Streaming error: {e}")
        return False


