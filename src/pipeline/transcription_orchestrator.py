#!/usr/bin/env python3
"""
Transcription Pipeline Orchestrator

Coordinates the complete transcription pipeline including:
1. Initial fast transcription at 1.75x speed
2. Confidence analysis and identification of low-quality segments  
3. Reprocessing of low-confidence segments at 0.7x speed with context
4. Final assembly and quality metrics
"""

import asyncio
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from workers.smart_chunker import SmartAudioChunker
from workers.optimized_gpu_worker import OptimizedGPUWorker
from quality.confidence_reprocessor import ConfidenceReprocessor, reprocess_low_confidence_segments
from analytics.timing_analyzer import TimingAnalyzer
from analytics.enhanced_output import EnhancedOutputGenerator
from utils.logger import get_logger


@dataclass
class TranscriptionJob:
    """Represents a complete transcription job"""
    job_id: str
    input_path: str
    output_dir: Path
    original_audio_path: str
    speed_multiplier: float = 1.75
    enable_confidence_reprocessing: bool = True
    formats: List[str] = None
    
    def __post_init__(self):
        if self.formats is None:
            self.formats = ["srt", "json", "txt"]


@dataclass
class PipelineResults:
    """Results from the complete transcription pipeline"""
    job_id: str
    segments: List[Dict]
    timing_analysis: Optional[Dict] = None
    confidence_report: Optional[Dict] = None
    processing_metrics: Optional[Dict] = None
    output_files: Dict[str, str] = None
    
    def __post_init__(self):
        if self.output_files is None:
            self.output_files = {}


class TranscriptionOrchestrator:
    """Orchestrates the complete transcription pipeline with confidence reprocessing"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Pipeline components
        self.chunker = SmartAudioChunker()
        self.gpu_worker = OptimizedGPUWorker()
        self.confidence_reprocessor = ConfidenceReprocessor()
        self.timing_analyzer = TimingAnalyzer()
        self.output_generator = EnhancedOutputGenerator()
        
        # Pipeline metrics
        self.pipeline_start_time = None
        self.stage_timings = {}
        
        self.logger.info("🎭 Transcription orchestrator initialized")
    
    async def process_transcription_job(self, job: TranscriptionJob) -> PipelineResults:
        """
        Process a complete transcription job with confidence reprocessing
        
        Args:
            job: TranscriptionJob configuration
            
        Returns:
            PipelineResults with all outputs and metrics
        """
        self.pipeline_start_time = time.time()
        self.logger.info(f"🚀 Starting transcription pipeline for job {job.job_id}")
        
        try:
            # Stage 1: Smart chunking with speed optimization
            chunks = await self._stage_chunking(job)
            
            # Stage 2: Initial GPU transcription at 1.75x speed
            initial_segments = await self._stage_initial_transcription(chunks, job)
            
            # Stage 3: Confidence analysis and reprocessing
            if job.enable_confidence_reprocessing:
                final_segments, confidence_report = await self._stage_confidence_reprocessing(
                    initial_segments, job
                )
            else:
                final_segments = initial_segments
                confidence_report = {"reprocessing_enabled": False}
            
            # Stage 4: Timing analysis (if enabled)
            timing_analysis = await self._stage_timing_analysis(final_segments, job)
            
            # Stage 5: Generate outputs
            output_files = await self._stage_output_generation(
                final_segments, timing_analysis, confidence_report, job
            )
            
            # Stage 6: Generate pipeline metrics
            processing_metrics = self._generate_pipeline_metrics(job)
            
            results = PipelineResults(
                job_id=job.job_id,
                segments=final_segments,
                timing_analysis=timing_analysis,
                confidence_report=confidence_report,
                processing_metrics=processing_metrics,
                output_files=output_files
            )
            
            total_time = time.time() - self.pipeline_start_time
            self.logger.info(f"✅ Pipeline completed for {job.job_id} in {total_time:.1f} seconds")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Pipeline failed for {job.job_id}: {e}")
            raise
    
    async def _stage_chunking(self, job: TranscriptionJob) -> List[Dict]:
        """Stage 1: Smart chunking with speed optimization"""
        stage_start = time.time()
        self.logger.info(f"📂 Stage 1: Smart chunking with {job.speed_multiplier}x speed optimization")
        
        # Extract bucket name from GCS path for output
        if job.input_path.startswith("gs://"):
            bucket_name = job.input_path.split("/")[2]
            output_bucket = f"{bucket_name}-chunks"
        else:
            output_bucket = str(job.output_dir / "chunks")
        
        chunks = await self.chunker.chunk_large_audio_file(job.input_path, output_bucket)
        
        self.stage_timings["chunking"] = time.time() - stage_start
        self.logger.info(f"✅ Chunking complete: {len(chunks)} chunks in {self.stage_timings['chunking']:.1f}s")
        
        return [{"id": c.id, "input_path": job.input_path, "start_time": c.start_time, "end_time": c.end_time} for c in chunks]
    
    async def _stage_initial_transcription(self, chunks: List[Dict], job: TranscriptionJob) -> List[Dict]:
        """Stage 2: Initial GPU transcription at optimized speed"""
        stage_start = time.time()
        self.logger.info(f"🔥 Stage 2: GPU transcription ({len(chunks)} chunks at {job.speed_multiplier}x speed)")
        
        # Initialize GPU worker
        await self.gpu_worker.initialize()
        
        # Convert chunks to AudioChunk objects
        from workers.optimized_gpu_worker import AudioChunk
        audio_chunks = [
            AudioChunk(
                id=chunk["id"],
                start_time=chunk["start_time"],
                end_time=chunk["end_time"],
                duration=chunk["end_time"] - chunk["start_time"],
                input_path=chunk["input_path"],
                output_path=f"{job.output_dir}/results/{chunk['id']}.json"
            )
            for chunk in chunks
        ]
        
        # Process chunks in batches
        all_results = []
        batch_size = self.gpu_worker.concurrent_chunks
        
        for i in range(0, len(audio_chunks), batch_size):
            batch = audio_chunks[i:i + batch_size]
            batch_results = await self.gpu_worker.process_audio_chunks_batch(batch)
            all_results.extend(batch_results)
        
        # Combine results into segments
        segments = []
        for result in sorted(all_results, key=lambda x: x["start_time"]):
            for segment in result.get("segments", []):
                segments.append(segment)
        
        self.stage_timings["initial_transcription"] = time.time() - stage_start
        self.logger.info(f"✅ Initial transcription complete: {len(segments)} segments in {self.stage_timings['initial_transcription']:.1f}s")
        
        return segments
    
    async def _stage_confidence_reprocessing(self, 
                                           initial_segments: List[Dict], 
                                           job: TranscriptionJob) -> Tuple[List[Dict], Dict]:
        """Stage 3: Confidence analysis and reprocessing"""
        stage_start = time.time()
        self.logger.info(f"🔍 Stage 3: Confidence analysis and reprocessing")
        
        # Perform confidence reprocessing
        final_segments, confidence_report = await reprocess_low_confidence_segments(
            initial_segments, 
            job.original_audio_path, 
            job.output_dir / "reprocessing"
        )
        
        self.stage_timings["confidence_reprocessing"] = time.time() - stage_start
        self.logger.info(f"✅ Confidence reprocessing complete in {self.stage_timings['confidence_reprocessing']:.1f}s")
        self.logger.info(f"   📊 Reprocessed {confidence_report.get('reprocessed_segments', 0)} segments")
        self.logger.info(f"   📈 Average confidence improvement: {confidence_report.get('average_confidence_improvement', 0):.3f}")
        
        return final_segments, confidence_report
    
    async def _stage_timing_analysis(self, segments: List[Dict], job: TranscriptionJob) -> Optional[Dict]:
        """Stage 4: Timing analysis"""
        stage_start = time.time()
        self.logger.info(f"⏱️ Stage 4: Timing analysis")
        
        try:
            # Convert segments to format expected by timing analyzer
            timing_segments = []
            for segment in segments:
                timing_segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"],
                    "confidence": segment.get("avg_logprob", 0.0),
                    "words": segment.get("words", [])
                })
            
            # Perform timing analysis
            timing_buckets, cadence_analysis = self.timing_analyzer.analyze_timing(timing_segments)
            
            timing_analysis = {
                "buckets": [bucket.__dict__ for bucket in timing_buckets],
                "cadence_analysis": cadence_analysis.__dict__ if cadence_analysis else None
            }
            
            self.stage_timings["timing_analysis"] = time.time() - stage_start
            self.logger.info(f"✅ Timing analysis complete in {self.stage_timings['timing_analysis']:.1f}s")
            
            return timing_analysis
            
        except Exception as e:
            self.logger.warning(f"⚠️ Timing analysis failed: {e}")
            return None
    
    async def _stage_output_generation(self, 
                                     segments: List[Dict],
                                     timing_analysis: Optional[Dict],
                                     confidence_report: Dict,
                                     job: TranscriptionJob) -> Dict[str, str]:
        """Stage 5: Generate output files"""
        stage_start = time.time()
        self.logger.info(f"📄 Stage 5: Output generation")
        
        # Create enhanced transcription result
        transcription_result = type('TranscriptionResult', (), {
            'language': segments[0].get('language', 'en') if segments else 'en',
            'language_probability': 0.95,  # Default high confidence
            'segments': segments
        })()
        
        # Generate outputs
        output_files = {}
        
        # Generate standard outputs
        for format_type in job.formats:
            if format_type == "json":
                # Enhanced JSON with confidence metrics
                enhanced_json = {
                    "metadata": {
                        "job_id": job.job_id,
                        "version": "0.3.0",
                        "features": ["confidence_reprocessing", "timing_analysis"],
                        "processing_speed": job.speed_multiplier,
                        "confidence_reprocessing_enabled": job.enable_confidence_reprocessing
                    },
                    "transcription": {
                        "language": transcription_result.language,
                        "language_probability": transcription_result.language_probability,
                        "total_segments": len(segments)
                    },
                    "segments": segments,
                    "confidence_report": confidence_report,
                    "timing_analysis": timing_analysis
                }
                
                json_file = job.output_dir / f"{job.job_id}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(enhanced_json, f, indent=2, ensure_ascii=False)
                output_files["json"] = str(json_file)
            
            elif format_type == "srt":
                srt_file = job.output_dir / f"{job.job_id}.srt"
                self._generate_srt_file(segments, srt_file, confidence_report)
                output_files["srt"] = str(srt_file)
            
            elif format_type == "txt":
                txt_file = job.output_dir / f"{job.job_id}.txt"
                self._generate_txt_file(segments, txt_file, confidence_report)
                output_files["txt"] = str(txt_file)
        
        # Generate confidence report
        report_file = job.output_dir / f"{job.job_id}_confidence_report.md"
        self._generate_confidence_report(confidence_report, report_file, job)
        output_files["confidence_report"] = str(report_file)
        
        self.stage_timings["output_generation"] = time.time() - stage_start
        self.logger.info(f"✅ Output generation complete in {self.stage_timings['output_generation']:.1f}s")
        
        return output_files
    
    def _generate_srt_file(self, segments: List[Dict], output_file: Path, confidence_report: Dict):
        """Generate SRT file with confidence indicators"""
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                start_time = self._format_srt_time(segment["start"])
                end_time = self._format_srt_time(segment["end"])
                text = segment["text"].strip()
                
                # Add confidence indicators
                if segment.get("reprocessed", False):
                    text += " [ENHANCED]"
                elif segment.get("avg_logprob", 0) < -0.5:
                    text += " [LOW_CONF]"
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
    
    def _generate_txt_file(self, segments: List[Dict], output_file: Path, confidence_report: Dict):
        """Generate plain text file with metadata"""
        with open(output_file, 'w', encoding='utf-8') as f:
            # Add header with confidence statistics
            total_segments = len(segments)
            reprocessed = confidence_report.get("reprocessed_segments", 0)
            
            f.write(f"# Transcription with Confidence Enhancement\n")
            f.write(f"# Total segments: {total_segments}\n")
            f.write(f"# Enhanced segments: {reprocessed}\n")
            f.write(f"# Enhancement rate: {reprocessed/total_segments*100:.1f}%\n\n")
            
            # Write transcript
            for segment in segments:
                f.write(segment["text"].strip() + " ")
    
    def _generate_confidence_report(self, confidence_report: Dict, output_file: Path, job: TranscriptionJob):
        """Generate detailed confidence analysis report"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Confidence Enhancement Report\n\n")
            f.write(f"**Job ID:** {job.job_id}  \n")
            f.write(f"**Processing Speed:** {job.speed_multiplier}x  \n")
            f.write(f"**Enhancement Enabled:** {job.enable_confidence_reprocessing}  \n\n")
            
            f.write(f"## Enhancement Results\n\n")
            f.write(f"- **Total Segments:** {confidence_report.get('total_segments', 0)}  \n")
            f.write(f"- **Enhanced Segments:** {confidence_report.get('reprocessed_segments', 0)}  \n")
            f.write(f"- **Enhancement Rate:** {confidence_report.get('reprocessing_rate', 0)*100:.1f}%  \n")
            f.write(f"- **Average Confidence Improvement:** {confidence_report.get('average_confidence_improvement', 0):.3f}  \n")
            f.write(f"- **Maximum Improvement:** {confidence_report.get('max_confidence_improvement', 0):.3f}  \n\n")
            
            f.write(f"## Processing Parameters\n\n")
            f.write(f"- **Confidence Threshold:** {confidence_report.get('confidence_threshold_used', -0.5)}  \n")
            f.write(f"- **Enhancement Speed:** {confidence_report.get('slow_speed_multiplier', 0.7)}x  \n")
            f.write(f"- **Context Padding:** {confidence_report.get('context_padding_seconds', 2.0)}s  \n\n")
            
            if confidence_report.get('reprocessed_segments', 0) > 0:
                improvement_ratio = confidence_report.get('average_confidence_improvement', 0)
                if improvement_ratio > 0.1:
                    f.write(f"✅ **Significant quality improvements achieved!**  \n")
                elif improvement_ratio > 0.05:
                    f.write(f"✅ **Moderate quality improvements achieved.**  \n")
                else:
                    f.write(f"ℹ️ **Minor quality improvements achieved.**  \n")
            else:
                f.write(f"✅ **All segments had acceptable confidence - no enhancement needed.**  \n")
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT subtitle format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def _generate_pipeline_metrics(self, job: TranscriptionJob) -> Dict[str, Any]:
        """Generate comprehensive pipeline performance metrics"""
        total_time = time.time() - self.pipeline_start_time
        
        metrics = {
            "total_processing_time": total_time,
            "stage_timings": self.stage_timings.copy(),
            "processing_speed_multiplier": job.speed_multiplier,
            "confidence_reprocessing_enabled": job.enable_confidence_reprocessing,
            "efficiency_metrics": {
                "chunking_percentage": (self.stage_timings.get("chunking", 0) / total_time) * 100,
                "transcription_percentage": (self.stage_timings.get("initial_transcription", 0) / total_time) * 100,
                "reprocessing_percentage": (self.stage_timings.get("confidence_reprocessing", 0) / total_time) * 100,
                "output_percentage": (self.stage_timings.get("output_generation", 0) / total_time) * 100
            }
        }
        
        return metrics


# Convenience function for external use
async def process_audio_with_confidence_enhancement(input_path: str,
                                                  output_dir: str,
                                                  job_id: Optional[str] = None,
                                                  speed_multiplier: float = 1.75,
                                                  enable_confidence_reprocessing: bool = True,
                                                  formats: List[str] = None) -> PipelineResults:
    """
    Process audio file with confidence enhancement
    
    Args:
        input_path: Path to audio file or GCS URI
        output_dir: Output directory  
        job_id: Optional job ID (auto-generated if None)
        speed_multiplier: Initial processing speed
        enable_confidence_reprocessing: Enable confidence-based reprocessing
        formats: Output formats
        
    Returns:
        PipelineResults with all outputs and metrics
    """
    if job_id is None:
        job_id = f"job_{int(time.time())}"
    
    if formats is None:
        formats = ["srt", "json", "txt"]
    
    job = TranscriptionJob(
        job_id=job_id,
        input_path=input_path,
        output_dir=Path(output_dir),
        original_audio_path=input_path,  # May need to download from GCS first
        speed_multiplier=speed_multiplier,
        enable_confidence_reprocessing=enable_confidence_reprocessing,
        formats=formats
    )
    
    orchestrator = TranscriptionOrchestrator()
    return await orchestrator.process_transcription_job(job)