#!/usr/bin/env python3

"""
Optimized GPU worker for high-performance audio transcription
Designed to process 6.8-hour audio files in 30-60 minutes
"""

import asyncio
import concurrent.futures
import time
import os
import json
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# GPU and ML imports
import torch
import torch.multiprocessing as mp
from faster_whisper import WhisperModel

# Async processing
import aioredis
import aiofiles
from google.cloud import storage

@dataclass
class AudioChunk:
    """Represents a chunk of audio to be processed"""
    id: str
    start_time: float
    end_time: float
    duration: float
    input_path: str
    output_path: str
    priority: int = 0  # Higher priority chunks processed first

class OptimizedGPUWorker:
    """High-performance GPU worker with async processing"""
    
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.model = None
        self.redis_pool = None
        self.storage_client = storage.Client()
        
        # Performance settings
        self.concurrent_chunks = int(os.getenv("CONCURRENT_CHUNKS", "4"))
        self.preload_model = os.getenv("PRELOAD_MODEL", "true").lower() == "true"
        self.streaming_mode = os.getenv("STREAMING_MODE", "true").lower() == "true"
        self.speed_multiplier = float(os.getenv("SPEED_MULTIPLIER", "1.75"))
        
        # Shared model cache across workers
        self.model_cache_path = os.getenv("MODEL_CACHE_PATH", "/model-cache")
        os.makedirs(self.model_cache_path, exist_ok=True)
        
        print(f"🚀 GPU Worker initialized - Device: {self.device}, Concurrent: {self.concurrent_chunks}")
    
    async def initialize(self):
        """Initialize worker with model preloading and Redis connection"""
        print("📥 Initializing optimized GPU worker...")
        
        # Initialize Redis connection pool
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_pool = aioredis.ConnectionPool.from_url(redis_url)
        
        # Preload model in background if enabled
        if self.preload_model:
            await self._preload_whisper_model()
        
        print("✅ GPU worker initialization complete")
    
    async def _preload_whisper_model(self):
        """Preload Whisper model for faster processing"""
        print("📦 Preloading Whisper model...")
        start_time = time.time()
        
        try:
            # Check if model is cached
            cached_model_path = os.path.join(self.model_cache_path, "large-v3")
            
            if os.path.exists(cached_model_path):
                print("📋 Using cached model")
                self.model = WhisperModel(cached_model_path, 
                                        device=self.device, 
                                        compute_type=self.compute_type)
            else:
                print("⬇️ Downloading model...")
                self.model = WhisperModel("large-v3", 
                                        device=self.device, 
                                        compute_type=self.compute_type,
                                        download_root=self.model_cache_path)
            
            # Warm up model with empty audio
            print("🔥 Warming up model...")
            import numpy as np
            dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
            list(self.model.transcribe(dummy_audio, beam_size=1))
            
            load_time = time.time() - start_time
            print(f"✅ Model preloaded in {load_time:.1f} seconds")
            
        except Exception as e:
            print(f"❌ Model preloading failed: {e}")
            self.model = None
    
    async def process_audio_chunks_batch(self, chunks: List[AudioChunk]) -> List[Dict]:
        """Process multiple audio chunks in parallel"""
        print(f"🔄 Processing batch of {len(chunks)} chunks")
        
        # Create semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(self.concurrent_chunks)
        
        async def process_single_chunk(chunk: AudioChunk):
            async with semaphore:
                return await self._process_chunk_async(chunk)
        
        # Process all chunks concurrently
        tasks = [process_single_chunk(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_count = len(results) - len(successful_results)
        
        if failed_count > 0:
            print(f"⚠️ {failed_count} chunks failed processing")
        
        print(f"✅ Batch processing complete: {len(successful_results)}/{len(chunks)} successful")
        return successful_results
    
    async def _process_chunk_async(self, chunk: AudioChunk) -> Dict:
        """Process a single audio chunk asynchronously"""
        try:
            # Download chunk from cloud storage
            audio_data = await self._download_chunk(chunk.input_path)
            
            # Process with Whisper in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(
                    executor, 
                    self._transcribe_chunk_sync, 
                    audio_data, 
                    chunk
                )
            
            # Upload result
            await self._upload_result(result, chunk.output_path)
            
            return result
            
        except Exception as e:
            print(f"❌ Error processing chunk {chunk.id}: {e}")
            raise
    
    def _transcribe_chunk_sync(self, audio_data: bytes, chunk: AudioChunk) -> Dict:
        """Synchronous transcription (runs in thread pool)"""
        if not self.model:
            # Lazy load model if not preloaded
            self.model = WhisperModel("large-v3", 
                                    device=self.device, 
                                    compute_type=self.compute_type)
        
        # Save audio data temporarily
        temp_path = f"/tmp/chunk_{chunk.id}.wav"
        with open(temp_path, 'wb') as f:
            f.write(audio_data)
        
        try:
            # Determine transcription parameters based on chunk priority
            # High priority chunks (reprocessing) get enhanced settings
            is_reprocessing = getattr(chunk, 'is_reprocessing', False)
            
            if is_reprocessing:
                # Enhanced settings for confidence reprocessing
                segments, info = self.model.transcribe(
                    temp_path,
                    beam_size=10,  # Increased beam size for better accuracy
                    temperature=0.0,  # Deterministic output
                    word_timestamps=True,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=100,  # More sensitive to speech
                        speech_pad_ms=200  # More padding around speech
                    ),
                    condition_on_previous_text=True,  # Use context
                    compression_ratio_threshold=2.4,  # More strict
                    logprob_threshold=-1.0,  # Accept lower confidence during reprocessing
                    no_speech_threshold=0.6  # Be more permissive of speech
                )
            else:
                # Standard optimized settings for fast processing
                segments, info = self.model.transcribe(
                    temp_path,
                    beam_size=5,
                    word_timestamps=True,
                    vad_filter=True,  # Voice activity detection
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
            
            # Convert to JSON-serializable format with timestamp correction
            result = {
                "chunk_id": chunk.id,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "language": info.language,
                "language_probability": info.language_probability,
                "speed_multiplier": self.speed_multiplier,
                "segments": []
            }
            
            for segment in segments:
                # Convert sped-up timestamps back to original timescale
                original_start = (segment.start * self.speed_multiplier) + chunk.start_time
                original_end = (segment.end * self.speed_multiplier) + chunk.start_time
                
                result["segments"].append({
                    "start": original_start,  # Original timescale
                    "end": original_end,      # Original timescale
                    "text": segment.text,
                    "confidence": getattr(segment, 'avg_logprob', 0.0),
                    "words": [
                        {
                            "start": (word.start * self.speed_multiplier) + chunk.start_time,  # Original timescale
                            "end": (word.end * self.speed_multiplier) + chunk.start_time,      # Original timescale
                            "text": word.word,
                            "confidence": word.probability
                        }
                        for word in getattr(segment, 'words', [])
                    ]
                })
            
            return result
            
        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    async def _download_chunk(self, gcs_path: str) -> bytes:
        """Download audio chunk from Google Cloud Storage"""
        bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        return blob.download_as_bytes()
    
    async def _upload_result(self, result: Dict, gcs_output_path: str):
        """Upload transcription result to Cloud Storage"""
        bucket_name, blob_path = gcs_output_path.replace("gs://", "").split("/", 1)
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Upload as JSON
        result_json = json.dumps(result, indent=2)
        blob.upload_from_string(result_json, content_type='application/json')
    
    async def run_worker_loop(self):
        """Main worker loop - processes chunks from Redis queue"""
        redis = aioredis.Redis(connection_pool=self.redis_pool)
        
        print("🔄 Starting optimized GPU worker loop...")
        
        while True:
            try:
                # Get batch of chunks from Redis queue
                chunk_data = await redis.blpop("gpu_chunks", timeout=30)
                if not chunk_data:
                    continue
                
                # Parse chunk information
                _, chunk_json = chunk_data
                chunk_info = json.loads(chunk_json)
                chunk = AudioChunk(**chunk_info)
                
                # Collect batch of chunks for parallel processing
                chunks = [chunk]
                
                # Try to get more chunks for batch processing (non-blocking)
                for _ in range(self.concurrent_chunks - 1):
                    try:
                        additional_chunk_data = await redis.blpop("gpu_chunks", timeout=0.1)
                        if additional_chunk_data:
                            _, additional_chunk_json = additional_chunk_data
                            additional_chunk_info = json.loads(additional_chunk_json)
                            chunks.append(AudioChunk(**additional_chunk_info))
                    except:
                        break
                
                # Process batch
                await self.process_audio_chunks_batch(chunks)
                
                # Update progress in Redis
                await redis.incrby("processed_chunks", len(chunks))
                
            except Exception as e:
                print(f"❌ Worker loop error: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying

async def main():
    """Main entry point for optimized GPU worker"""
    worker = OptimizedGPUWorker()
    await worker.initialize()
    await worker.run_worker_loop()

if __name__ == "__main__":
    # Enable multiprocessing support
    mp.set_start_method('spawn', force=True)
    
    # Run async worker
    asyncio.run(main())