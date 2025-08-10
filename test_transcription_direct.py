#!/usr/bin/env python3
"""
Direct transcription test bypassing CLI to isolate the issue.
"""

# CRITICAL: Set environment variables BEFORE any other imports to prevent OpenMP conflicts
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['MKL_NUM_THREADS'] = '8'
os.environ['PYTHONUNBUFFERED'] = '1'

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_direct_transcription():
    """Test transcription directly without CLI."""
    print("🎯 Direct Transcription Test")
    print("=" * 40)
    
    video_path = Path("processing/x.com_elder_plinius_status_1945128977766441106_01.mp4")
    
    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        return False
    
    try:
        print("📋 Step 1: Loading configuration...")
        from utils.config import load_config
        config = load_config("default")
        print(f"   ✅ Config loaded: {config.transcription.model_size}")
        
        print("📋 Step 2: Setting up logging...")
        from utils.logger import setup_logging
        logger = setup_logging(config.logging)
        print("   ✅ Logger ready")
        
        print("📋 Step 3: Processing file...")
        from core.file_processor import FileProcessor
        processor = FileProcessor()
        
        output_dir = Path("processing/test_output")
        output_dir.mkdir(exist_ok=True)
        
        # Process the file
        result = processor.process_file(
            video_path,
            output_dir / "processed",
            speed_multiplier=1.0,  # No speed change for testing
            remove_silence=False,   # Skip silence removal for speed
            normalize=True
        )
        
        print(f"   ✅ File processed: {result.processed_path}")
        print(f"   📊 Duration: {result.processed_info.duration:.1f}s")
        
        print("📋 Step 4: Creating transcriber...")
        from core.transcriber import WhisperTranscriber
        
        # Use smaller model and explicit settings for testing
        transcriber = WhisperTranscriber(
            model_size="base",      # Smaller model for faster testing
            device="cpu",           # Explicit CPU
            compute_type="int8"     # CPU-compatible
        )
        print("   ✅ Transcriber ready")
        
        print("📋 Step 5: Chunking audio...")
        from core.chunker import SmartChunker
        
        chunker = SmartChunker(
            chunk_size=30,          # 30 second chunks
            overlap_duration=2,     # 2 second overlap
            silence_threshold=-40
        )
        
        chunking_result = chunker.chunk_audio(
            result.processed_path,
            output_dir / "chunks",
            remove_silence=False
        )
        
        print(f"   ✅ Audio chunked: {chunking_result.total_chunks} chunks")
        
        print("📋 Step 6: Transcribing...")
        
        # Transcribe just the first chunk for testing
        if chunking_result.chunks:
            first_chunk = chunking_result.chunks[0]
            print(f"   🎯 Transcribing first chunk: {first_chunk.duration:.1f}s")
            
            chunk_result = transcriber.transcribe_chunk(
                first_chunk,
                language=None,  # Auto-detect
                temperature=0.0,
                beam_size=5
            )
            
            print(f"   ✅ Transcription complete!")
            print(f"   📝 Text: {chunk_result.text[:100]}...")
            print(f"   📊 Confidence: {chunk_result.avg_confidence:.2f}")
            print(f"   ⏱️  Time: {chunk_result.processing_time:.2f}s")
            
            # Save the result
            output_file = output_dir / "test_transcription.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Transcription Test Result\n")
                f.write(f"========================\n\n")
                f.write(f"File: {video_path.name}\n")
                f.write(f"Duration: {first_chunk.duration:.1f}s\n")
                f.write(f"Language: {chunk_result.language}\n")
                f.write(f"Confidence: {chunk_result.avg_confidence:.2f}\n")
                f.write(f"Processing Time: {chunk_result.processing_time:.2f}s\n\n")
                f.write(f"Text:\n{chunk_result.text}\n")
            
            print(f"   💾 Results saved to: {output_file}")
            
            return True
        else:
            print("   ❌ No chunks created")
            return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_direct_transcription()
    print(f"\n🎯 Result: {'SUCCESS' if success else 'FAILED'}")
    sys.exit(0 if success else 1)