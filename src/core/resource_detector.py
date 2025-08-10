"""
TalkGPT Resource Detection Module

Cross-platform hardware detection and optimization for CPU/GPU resources.
Automatically determines optimal processing configuration based on available hardware.
"""

import os
import platform
import psutil
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False

try:
    from ..utils.logger import get_logger
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.logger import get_logger


@dataclass
class HardwareInfo:
    """Hardware information container."""
    cpu_cores: int
    memory_gb: float
    gpu_available: bool
    gpu_count: int
    gpu_memory: list
    gpu_names: list
    platform: str
    mps_available: bool
    recommended_device: str
    optimal_workers: int


class ResourceDetector:
    """
    Hardware resource detection and optimization system.
    
    Detects available CPU, GPU, and memory resources across platforms
    and provides recommendations for optimal processing configuration.
    """
    
    def __init__(self):
        """Initialize the resource detector."""
        self.logger = get_logger("talkgpt.resources")
        self._hardware_info: Optional[HardwareInfo] = None
    
    def detect_hardware(self) -> HardwareInfo:
        """
        Detect all available hardware resources.
        
        Returns:
            HardwareInfo object with complete hardware information
        """
        if self._hardware_info is not None:
            return self._hardware_info
        
        self.logger.info("Detecting hardware resources...")
        
        # Basic system information
        cpu_cores = os.cpu_count() or 1
        memory_info = psutil.virtual_memory()
        memory_gb = memory_info.total / (1024**3)
        platform_name = platform.system()
        
        # GPU detection
        gpu_info = self._detect_gpu()
        
        # MPS detection (Apple Silicon)
        mps_available = self._detect_mps()
        
        # Determine recommended device
        recommended_device = self._get_recommended_device(
            gpu_info['available'], 
            gpu_info['count'], 
            mps_available
        )
        
        # Calculate optimal worker count
        optimal_workers = self._calculate_optimal_workers(
            cpu_cores, 
            memory_gb, 
            gpu_info['count'],
            recommended_device
        )
        
        self._hardware_info = HardwareInfo(
            cpu_cores=cpu_cores,
            memory_gb=memory_gb,
            gpu_available=gpu_info['available'],
            gpu_count=gpu_info['count'],
            gpu_memory=gpu_info['memory'],
            gpu_names=gpu_info['names'],
            platform=platform_name,
            mps_available=mps_available,
            recommended_device=recommended_device,
            optimal_workers=optimal_workers
        )
        
        self.logger.info(f"Hardware detection complete: {self._hardware_info}")
        return self._hardware_info
    
    def _detect_gpu(self) -> Dict[str, Any]:
        """
        Detect GPU availability and specifications.
        
        Returns:
            Dictionary with GPU information
        """
        gpu_info = {
            'available': False,
            'count': 0,
            'memory': [],
            'names': []
        }
        
        if not TORCH_AVAILABLE:
            self.logger.warning("PyTorch not available, GPU detection disabled")
            return gpu_info
        
        # NVIDIA CUDA detection
        if torch.cuda.is_available():
            gpu_info['available'] = True
            gpu_info['count'] = torch.cuda.device_count()
            
            for i in range(gpu_info['count']):
                props = torch.cuda.get_device_properties(i)
                gpu_info['memory'].append(props.total_memory)
                gpu_info['names'].append(props.name)
                
                self.logger.info(f"CUDA GPU {i}: {props.name} ({props.total_memory / 1024**3:.1f} GB)")
        
        # AMD ROCm detection (if available) - skip for now as it's complex
        # elif hasattr(torch.backends, 'rocm') and torch.backends.rocm.is_available():
        #     self.logger.info("AMD ROCm GPU detected")
        #     gpu_info['available'] = True
        #     gpu_info['count'] = 1  # Simplified for ROCm
        
        # Additional GPU detection using GPUtil (fallback)
        elif GPUTIL_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_info['available'] = True
                    gpu_info['count'] = len(gpus)
                    for gpu in gpus:
                        gpu_info['memory'].append(gpu.memoryTotal * 1024**2)  # Convert MB to bytes
                        gpu_info['names'].append(gpu.name)
                        self.logger.info(f"GPU detected: {gpu.name} ({gpu.memoryTotal} MB)")
            except Exception as e:
                self.logger.warning(f"GPUtil detection failed: {e}")
        
        if not gpu_info['available']:
            self.logger.info("No GPU detected, will use CPU processing")
        
        return gpu_info
    
    def _detect_mps(self) -> bool:
        """
        Detect Apple Metal Performance Shaders (MPS) availability.
        
        Returns:
            True if MPS is available, False otherwise
        """
        if not TORCH_AVAILABLE:
            return False
        
        try:
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                self.logger.info("Apple MPS (Metal Performance Shaders) available")
                return True
        except Exception as e:
            self.logger.debug(f"MPS detection failed: {e}")
        
        return False
    
    def _get_recommended_device(self, 
                              gpu_available: bool, 
                              gpu_count: int, 
                              mps_available: bool) -> str:
        """
        Determine the recommended processing device.
        
        Args:
            gpu_available: Whether CUDA GPU is available
            gpu_count: Number of CUDA GPUs
            mps_available: Whether Apple MPS is available
            
        Returns:
            Recommended device string ('cuda', 'mps', or 'cpu')
        """
        if gpu_available and gpu_count > 0:
            return "cuda"
        elif mps_available:
            return "mps"
        else:
            return "cpu"
    
    def _calculate_optimal_workers(self, 
                                 cpu_cores: int, 
                                 memory_gb: float, 
                                 gpu_count: int,
                                 device: str) -> int:
        """
        Calculate optimal number of worker processes.
        
        Args:
            cpu_cores: Number of CPU cores
            memory_gb: Available memory in GB
            gpu_count: Number of GPUs
            device: Recommended device
            
        Returns:
            Optimal number of workers
        """
        if device == "cuda" and gpu_count > 0:
            # For GPU processing, typically one worker per GPU
            # But consider memory constraints (Whisper Large ~3GB per instance)
            max_gpu_workers = gpu_count
            
            # Estimate GPU memory constraint (assuming 8GB minimum per worker)
            if hasattr(self, '_hardware_info') and self._hardware_info and self._hardware_info.gpu_memory:
                min_gpu_memory = min(self._hardware_info.gpu_memory)
                memory_limited_workers = max(1, min_gpu_memory // (3 * 1024**3))  # 3GB per worker
                max_gpu_workers = min(max_gpu_workers, memory_limited_workers)
            
            return min(max_gpu_workers, 4)  # Cap at 4 for stability
        
        elif device == "mps":
            # Apple MPS typically works best with 1-2 workers
            return min(2, max(1, cpu_cores // 4))
        
        else:
            # CPU processing - use 50-70% of cores, limited by memory
            base_workers = max(1, int(cpu_cores * 0.6))
            
            # Memory constraint (assume 4GB per CPU worker for Whisper Large)
            memory_limited_workers = max(1, int(memory_gb // 4))
            
            return min(base_workers, memory_limited_workers, 8)  # Cap at 8
    
    def get_device_config(self, force_device: Optional[str] = None) -> Dict[str, Any]:
        """
        Get device configuration for model loading.
        
        Args:
            force_device: Force specific device ('cpu', 'cuda', 'mps')
            
        Returns:
            Device configuration dictionary
        """
        hardware = self.detect_hardware()
        
        if force_device:
            device = force_device
            self.logger.info(f"Device forced to: {device}")
        else:
            device = hardware.recommended_device
        
        # Auto-route accuracy-first compute types by device at runtime
        config = {
            'device': device,
            'device_index': 0 if device == 'cuda' else None,
            'compute_type': 'float16' if device in ('cuda', 'mps') else 'float32',
            'cpu_threads': self._get_optimal_cpu_threads(hardware.cpu_cores),
        }
        
        # GPU-specific configuration
        if device == 'cuda' and hardware.gpu_available:
            config['gpu_memory_fraction'] = 0.9
            config['allow_growth'] = True
        
        return config
    
    def _get_optimal_compute_type(self, device: str) -> str:
        """
        Get optimal compute type for the device.
        
        Args:
            device: Target device
            
        Returns:
            Optimal compute type
        """
        if device == 'cuda':
            return 'float16'  # Best balance of speed and accuracy on GPU
        elif device == 'mps':
            return 'float16'  # MPS supports float16
        else:
            return 'int8'     # CPU benefits from quantization
    
    def _get_optimal_cpu_threads(self, cpu_cores: int) -> int:
        """
        Get optimal CPU thread count.
        
        Args:
            cpu_cores: Number of CPU cores
            
        Returns:
            Optimal thread count
        """
        # Use 75% of cores, but leave at least 2 cores free
        return max(1, min(cpu_cores - 2, int(cpu_cores * 0.75)))
    
    def get_memory_info(self) -> Dict[str, float]:
        """
        Get current memory usage information.
        
        Returns:
            Memory information dictionary
        """
        memory = psutil.virtual_memory()
        
        info = {
            'total_gb': memory.total / (1024**3),
            'available_gb': memory.available / (1024**3),
            'used_gb': memory.used / (1024**3),
            'percent_used': memory.percent
        }
        
        # Add GPU memory if available
        if TORCH_AVAILABLE and torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                memory_allocated = torch.cuda.memory_allocated(i) / (1024**3)
                memory_reserved = torch.cuda.memory_reserved(i) / (1024**3)
                total_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                
                info[f'gpu_{i}_allocated_gb'] = memory_allocated
                info[f'gpu_{i}_reserved_gb'] = memory_reserved
                info[f'gpu_{i}_total_gb'] = total_memory
                info[f'gpu_{i}_free_gb'] = total_memory - memory_reserved
        
        return info
    
    def validate_configuration(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a processing configuration against available hardware.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        hardware = self.detect_hardware()
        
        # Check worker count
        max_workers = config.get('max_workers', hardware.optimal_workers)
        if max_workers > hardware.cpu_cores:
            return False, f"Worker count ({max_workers}) exceeds CPU cores ({hardware.cpu_cores})"
        
        # Check device availability
        device = config.get('device', 'auto')
        if device == 'cuda' and not hardware.gpu_available:
            return False, "CUDA device requested but no GPU available"
        
        if device == 'mps' and not hardware.mps_available:
            return False, "MPS device requested but not available"
        
        # Check memory requirements (rough estimate)
        model_size = config.get('model_size', 'large-v3')
        memory_per_worker = self._estimate_memory_usage(model_size, device)
        total_memory_needed = memory_per_worker * max_workers
        
        if total_memory_needed > hardware.memory_gb * 0.8:  # Leave 20% free
            return False, f"Estimated memory usage ({total_memory_needed:.1f}GB) exceeds available memory"
        
        return True, "Configuration valid"
    
    def _estimate_memory_usage(self, model_size: str, device: str) -> float:
        """
        Estimate memory usage for a model configuration.
        
        Args:
            model_size: Whisper model size
            device: Target device
            
        Returns:
            Estimated memory usage in GB
        """
        # Memory estimates for different model sizes (approximate)
        model_memory = {
            'tiny': 0.5,
            'base': 0.7,
            'small': 1.0,
            'medium': 2.0,
            'large': 3.0,
            'large-v2': 3.0,
            'large-v3': 3.2
        }
        
        base_memory = model_memory.get(model_size, 3.0)
        
        # Device-specific adjustments
        if device == 'cpu':
            return base_memory * 1.5  # CPU uses more memory
        else:
            return base_memory
    
    def get_benchmark_info(self) -> Dict[str, Any]:
        """
        Get hardware benchmark information for performance estimation.
        
        Returns:
            Benchmark information dictionary
        """
        hardware = self.detect_hardware()
        
        benchmark = {
            'cpu_score': self._estimate_cpu_performance(),
            'memory_bandwidth': self._estimate_memory_bandwidth(),
            'recommended_chunk_size': self._recommend_chunk_size(),
            'estimated_speedup': self._estimate_processing_speedup(hardware.recommended_device)
        }
        
        return benchmark
    
    def _estimate_cpu_performance(self) -> float:
        """Estimate CPU performance score (relative)."""
        # Simple heuristic based on core count and frequency
        cpu_cores = psutil.cpu_count(logical=False) or 1
        cpu_freq = psutil.cpu_freq()
        
        if cpu_freq:
            base_score = cpu_cores * (cpu_freq.current / 1000)  # Cores * GHz
        else:
            base_score = cpu_cores * 2.5  # Assume 2.5GHz average
        
        return base_score
    
    def _estimate_memory_bandwidth(self) -> str:
        """Estimate memory bandwidth category."""
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        if memory_gb >= 64:
            return "high"
        elif memory_gb >= 32:
            return "medium"
        else:
            return "low"
    
    def _recommend_chunk_size(self) -> int:
        """Recommend optimal chunk size based on hardware."""
        hardware = self.detect_hardware()
        
        if hardware.gpu_available:
            return 60  # Larger chunks for GPU
        elif hardware.memory_gb >= 16:
            return 45  # Medium chunks for good CPU systems
        else:
            return 30  # Smaller chunks for limited systems
    
    def _estimate_processing_speedup(self, device: str) -> float:
        """Estimate processing speedup compared to real-time."""
        if device == 'cuda':
            return 8.0  # GPU can be very fast
        elif device == 'mps':
            return 4.0  # Apple Silicon is quite fast
        else:
            return 2.0  # CPU baseline


# Global resource detector instance
_resource_detector: Optional[ResourceDetector] = None


def get_resource_detector() -> ResourceDetector:
    """Get the global resource detector instance."""
    global _resource_detector
    if _resource_detector is None:
        _resource_detector = ResourceDetector()
    return _resource_detector


def detect_hardware() -> HardwareInfo:
    """Detect hardware using the global detector."""
    return get_resource_detector().detect_hardware()


def get_device_config(force_device: Optional[str] = None) -> Dict[str, Any]:
    """Get device configuration using the global detector."""
    return get_resource_detector().get_device_config(force_device)