#!/usr/bin/env python3

"""
Smart audio chunker for optimized parallel processing
Uses voice activity detection and smart overlap strategies
"""

import asyncio
import os
import json
import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass
import aiofiles
from google.cloud import storage
import librosa
import soundfile as sf

@dataclass
class SmartChunk:
    """Represents an intelligently chunked audio segment"""
    id: str
    start_time: float
    end_time: float
    duration: float
    has_speech: bool
    silence_padding: float
    priority: int = 0

class SmartAudioChunker:
    """Intelligent audio chunker for optimal GPU processing with speed optimization"""
    
    def __init__(self):
        self.storage_client = storage.Client()
        
        # Speed optimization parameters
        self.speed_multiplier = 1.75  # Process audio at 1.75x speed
        
        # Chunking parameters (adjusted for sped-up audio)
        self.target_chunk_duration = 45  # seconds in original time
        self.target_chunk_duration_sped = self.target_chunk_duration / self.speed_multiplier  # ~25.7s in sped-up time
        self.overlap_duration = 3  # seconds in original time
        self.overlap_duration_sped = self.overlap_duration / self.speed_multiplier  # ~1.7s in sped-up time
        self.min_chunk_duration = 10  # seconds in original time
        self.max_chunk_duration = 60  # seconds in original time
        
        # Voice activity detection parameters
        self.sample_rate = 16000  # Whisper's expected sample rate
        self.hop_length = 512
        self.frame_length = 2048
        
        print(f"🧠 Smart chunker initialized - Speed: {self.speed_multiplier}x, Target duration: {self.target_chunk_duration}s original ({self.target_chunk_duration_sped:.1f}s sped-up)")
    
    async def chunk_large_audio_file(self, input_gcs_path: str, output_bucket: str) -> List[SmartChunk]:
        """
        Intelligently chunk a large audio file for optimal parallel processing
        """
        print(f"🔪 Smart chunking: {input_gcs_path}")
        
        # Download and analyze audio
        audio_data, duration = await self._download_and_analyze_audio(input_gcs_path)
        print(f"📊 Audio analysis complete - Duration: {duration:.1f}s")
        
        # Detect voice activity
        voice_activity = await self._detect_voice_activity(audio_data)
        print(f"🗣️ Voice activity detection complete")
        
        # Create smart chunks based on voice activity
        chunks = await self._create_smart_chunks(
            audio_data, voice_activity, duration, input_gcs_path, output_bucket
        )
        
        # Upload chunks in parallel
        await self._upload_chunks_parallel(chunks, audio_data)
        
        print(f"✅ Smart chunking complete: {len(chunks)} chunks created")
        return chunks
    
    async def _download_and_analyze_audio(self, gcs_path: str) -> Tuple[np.ndarray, float]:
        """Download audio file and convert to optimal format with speed optimization"""
        print("⬇️ Downloading audio file...")
        
        # Parse GCS path
        bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Download to temporary file
        temp_path = "/tmp/input_audio.wav"
        blob.download_to_filename(temp_path)
        
        # Load and resample audio
        print("🔄 Processing audio format...")
        audio_data, orig_sr = librosa.load(temp_path, sr=None)
        
        # Resample to Whisper's expected sample rate if needed
        if orig_sr != self.sample_rate:
            print(f"🔄 Resampling from {orig_sr}Hz to {self.sample_rate}Hz")
            audio_data = librosa.resample(audio_data, orig_sr=orig_sr, target_sr=self.sample_rate)
        
        original_duration = len(audio_data) / self.sample_rate
        
        # Apply speed optimization: increase playback speed by 1.75x
        print(f"⚡ Applying {self.speed_multiplier}x speed optimization...")
        # Use librosa's time stretching without pitch change
        audio_data_sped = librosa.effects.time_stretch(audio_data, rate=self.speed_multiplier)
        sped_duration = len(audio_data_sped) / self.sample_rate
        
        print(f"📊 Duration: {original_duration:.1f}s → {sped_duration:.1f}s ({self.speed_multiplier}x faster)")
        print(f"💡 Processing time reduced by {((original_duration - sped_duration) / original_duration * 100):.1f}%")
        
        # Clean up temp file
        os.unlink(temp_path)
        
        # Return sped-up audio with original duration for timestamp mapping
        return audio_data_sped, original_duration
    
    async def _detect_voice_activity(self, audio_data: np.ndarray) -> np.ndarray:
        """Detect voice activity using librosa"""
        print("🔍 Detecting voice activity...")
        
        # Use spectral rolloff and zero crossing rate for VAD
        # This is a simplified VAD - production might use more sophisticated methods
        
        # Compute short-time energy
        frame_length = int(0.025 * self.sample_rate)  # 25ms frames
        hop_length = int(0.010 * self.sample_rate)    # 10ms hop
        
        # Energy-based VAD
        frames = librosa.util.frame(audio_data, frame_length=frame_length, 
                                  hop_length=hop_length, axis=0)
        energy = np.sum(frames ** 2, axis=0)
        
        # Spectral centroid for voice detection
        spectral_centroids = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.sample_rate, hop_length=hop_length
        )[0]
        
        # Combine energy and spectral features
        energy_threshold = np.percentile(energy, 30)  # Adaptive threshold
        spectral_threshold = np.percentile(spectral_centroids, 40)
        
        # Voice activity: high energy AND reasonable spectral centroid
        voice_activity = (energy > energy_threshold) & (spectral_centroids > spectral_threshold)
        
        # Convert frame-based VAD to time-based
        time_vad = np.zeros(len(audio_data), dtype=bool)
        for i, is_voice in enumerate(voice_activity):
            start_sample = i * hop_length
            end_sample = min(start_sample + hop_length, len(audio_data))
            time_vad[start_sample:end_sample] = is_voice
        
        return time_vad
    
    async def _create_smart_chunks(self, audio_data: np.ndarray, voice_activity: np.ndarray, 
                                 original_duration: float, input_path: str, output_bucket: str) -> List[SmartChunk]:
        """Create intelligent chunks based on voice activity with speed compensation"""
        print("✂️ Creating smart chunks with timestamp mapping...")
        
        chunks = []
        current_time = 0.0  # Time in original audio
        chunk_id = 0
        
        # Calculate sped-up audio duration for processing
        sped_duration = len(audio_data) / self.sample_rate
        
        while current_time < original_duration:
            # Determine optimal chunk end time in original timescale
            target_end_time = current_time + self.target_chunk_duration
            
            # Find a good break point (silence) near the target end
            break_point = self._find_optimal_break_point(
                voice_activity, current_time, target_end_time, original_duration
            )
            
            # Create chunk
            chunk_duration = break_point - current_time
            
            # Skip very short chunks
            if chunk_duration < self.min_chunk_duration:
                current_time = break_point
                continue
            
            # Calculate speech ratio for prioritization (using sped-up audio samples)
            # Convert original time to sped-up audio samples
            start_sample = int((current_time / self.speed_multiplier) * self.sample_rate)
            end_sample = int((break_point / self.speed_multiplier) * self.sample_rate)
            end_sample = min(end_sample, len(voice_activity))
            
            if start_sample < len(voice_activity):
                chunk_vad = voice_activity[start_sample:end_sample]
                speech_ratio = np.sum(chunk_vad) / len(chunk_vad) if len(chunk_vad) > 0 else 0
            else:
                speech_ratio = 0
            
            # Create chunk with original timescale for final output
            chunk = SmartChunk(
                id=f"chunk_{chunk_id:04d}",
                start_time=max(0, current_time - self.overlap_duration/2),  # Original timescale
                end_time=min(original_duration, break_point + self.overlap_duration/2),  # Original timescale
                duration=chunk_duration + self.overlap_duration,  # Original timescale
                has_speech=speech_ratio > 0.1,  # 10% speech threshold
                silence_padding=self.overlap_duration/2,
                priority=int(speech_ratio * 100)  # Higher priority for more speech
            )
            
            chunks.append(chunk)
            chunk_id += 1
            current_time = break_point
        
        # Sort by priority (highest first) for optimal processing order
        chunks.sort(key=lambda x: x.priority, reverse=True)
        
        time_saved = original_duration - sped_duration
        print(f"📈 Created {len(chunks)} smart chunks with priorities")
        print(f"⚡ Speed optimization will save {time_saved/60:.1f} minutes of processing time")
        return chunks
    
    def _find_optimal_break_point(self, voice_activity: np.ndarray, start_time: float, 
                                target_end_time: float, total_duration: float) -> float:
        """Find optimal break point in silence"""
        
        # Convert to samples
        start_sample = int(start_time * self.sample_rate)
        target_end_sample = int(target_end_time * self.sample_rate)
        max_end_sample = int(min(target_end_time + 10, total_duration) * self.sample_rate)  # +10s flexibility
        
        # Look for silence window near target end
        search_start = max(target_end_sample - int(5 * self.sample_rate), start_sample)  # 5s before target
        search_end = min(max_end_sample, len(voice_activity))
        
        if search_start >= search_end:
            return min(target_end_time, total_duration)
        
        search_region = voice_activity[search_start:search_end]
        
        # Find longest silence period
        silence_mask = ~search_region
        best_break = target_end_sample
        max_silence_length = 0
        current_silence_start = None
        
        for i, is_silence in enumerate(silence_mask):
            if is_silence and current_silence_start is None:
                current_silence_start = i
            elif not is_silence and current_silence_start is not None:
                silence_length = i - current_silence_start
                if silence_length > max_silence_length:
                    max_silence_length = silence_length
                    # Break in middle of silence period
                    best_break = search_start + current_silence_start + silence_length // 2
                current_silence_start = None
        
        # Handle silence at end of search region
        if current_silence_start is not None:
            silence_length = len(silence_mask) - current_silence_start
            if silence_length > max_silence_length:
                best_break = search_start + current_silence_start + silence_length // 2
        
        return min(best_break / self.sample_rate, total_duration)
    
    async def _upload_chunks_parallel(self, chunks: List[SmartChunk], audio_data: np.ndarray):
        """Upload audio chunks to Cloud Storage in parallel"""
        print(f"⬆️ Uploading {len(chunks)} chunks in parallel...")
        
        async def upload_single_chunk(chunk: SmartChunk):
            # Extract chunk audio
            start_sample = int(chunk.start_time * self.sample_rate)
            end_sample = int(chunk.end_time * self.sample_rate)
            chunk_audio = audio_data[start_sample:end_sample]
            
            # Save to temporary file
            temp_path = f"/tmp/{chunk.id}.wav"
            sf.write(temp_path, chunk_audio, self.sample_rate)
            
            try:
                # Upload to GCS
                bucket = self.storage_client.bucket(chunk.output_bucket)
                blob = bucket.blob(f"chunks/{chunk.id}.wav")
                blob.upload_from_filename(temp_path)
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        # Upload all chunks in parallel (limit concurrency to avoid overwhelming storage)
        semaphore = asyncio.Semaphore(16)  # Max 16 concurrent uploads
        
        async def upload_with_semaphore(chunk):
            async with semaphore:
                await upload_single_chunk(chunk)
        
        await asyncio.gather(*[upload_with_semaphore(chunk) for chunk in chunks])
        print("✅ All chunks uploaded successfully")

async def main():
    """CLI entry point for smart chunker"""
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python smart_chunker.py <input_gcs_path> <output_bucket>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_bucket = sys.argv[2]
    
    chunker = SmartAudioChunker()
    chunks = await chunker.chunk_large_audio_file(input_path, output_bucket)
    
    # Output chunk information
    chunks_info = {
        "total_chunks": len(chunks),
        "total_duration": sum(c.duration for c in chunks),
        "chunks": [
            {
                "id": c.id,
                "start_time": c.start_time,
                "end_time": c.end_time,
                "duration": c.duration,
                "has_speech": c.has_speech,
                "priority": c.priority
            }
            for c in chunks
        ]
    }
    
    print(json.dumps(chunks_info, indent=2))

if __name__ == "__main__":
    asyncio.run(main())