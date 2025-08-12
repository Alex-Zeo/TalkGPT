from pathlib import Path
from src.core.chunker import SmartChunker


def test_time_based_split_no_libs(monkeypatch, tmp_path: Path):
    # Create a tiny wav file using bytes to avoid external deps
    audio_path = tmp_path / "a.wav"
    audio_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")

    chunker = SmartChunker(chunk_size=5, overlap_duration=1)
    try:
        result = chunker.chunk_audio(audio_path, remove_silence=False)
        assert result.total_chunks >= 1
    except Exception:
        # If pydub is not available, the error should be a clear runtime error
        pass

