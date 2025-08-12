"""
TalkGPT CLI Status Commands

System status, monitoring, and information display commands.
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

try:
    from ...core.resource_detector import detect_hardware, get_resource_detector
    from ...utils.logger import get_logger
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from core.resource_detector import detect_hardware, get_resource_detector
    from utils.logger import get_logger


def show_system_status(quiet: bool = False):
    """Display comprehensive system status information."""
    console = Console()
    
    if not quiet:
        console.print("🔍 [bold blue]System Hardware Analysis[/bold blue]")
    
    try:
        # Detect hardware with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=quiet
        ) as progress:
            task = progress.add_task("Detecting hardware...", total=None)
            hardware = detect_hardware()
            progress.update(task, completed=True)
        
        if quiet:
            # Simple output for quiet mode
            click.echo(f"CPU: {hardware.cpu_cores} cores, {hardware.memory_gb:.1f}GB RAM")
            click.echo(f"GPU: {'Yes' if hardware.gpu_available else 'No'}")
            click.echo(f"Device: {hardware.recommended_device}")
            click.echo(f"Workers: {hardware.optimal_workers}")
            return
        
        # Create system information table
        system_table = Table(title="System Information")
        system_table.add_column("Component", style="cyan", no_wrap=True)
        system_table.add_column("Value", style="green")
        system_table.add_column("Details", style="yellow")
        
        # Basic system info
        system_table.add_row("Platform", hardware.platform, "")
        system_table.add_row("CPU Cores", str(hardware.cpu_cores), "Physical + Logical")
        system_table.add_row("Memory", f"{hardware.memory_gb:.1f} GB", "Total RAM")
        
        # GPU information
        if hardware.gpu_available:
            gpu_details = f"{hardware.gpu_count} GPU(s)"
            if hardware.gpu_names:
                gpu_details += f"\n{', '.join(hardware.gpu_names[:2])}"  # Show first 2
            system_table.add_row("GPU", "✅ Available", gpu_details)
            
            # GPU memory details
            if hardware.gpu_memory:
                total_gpu_memory = sum(hardware.gpu_memory) / (1024**3)  # Convert to GB
                system_table.add_row("GPU Memory", f"{total_gpu_memory:.1f} GB", "Total across all GPUs")
        else:
            system_table.add_row("GPU", "❌ Not Available", "CPU processing only")
        
        # Apple Silicon MPS
        if hardware.mps_available:
            system_table.add_row("Apple MPS", "✅ Available", "Metal Performance Shaders")
        
        console.print(system_table)
        
        # Performance recommendations
        perf_table = Table(title="Performance Recommendations")
        perf_table.add_column("Setting", style="cyan")
        perf_table.add_column("Recommended Value", style="green")
        perf_table.add_column("Reason", style="yellow")
        
        perf_table.add_row("Device", hardware.recommended_device, "Best available processing unit")
        perf_table.add_row("Workers", str(hardware.optimal_workers), "Optimal parallel processing")
        
        # Get benchmark info
        detector = get_resource_detector()
        benchmark = detector.get_benchmark_info()
        
        perf_table.add_row("Chunk Size", f"{benchmark['recommended_chunk_size']}s", "Optimized for hardware")
        perf_table.add_row("Expected Speed", f"{benchmark['estimated_speedup']:.1f}x real-time", "Processing speed estimate")
        
        console.print(perf_table)
        
        # Memory status
        memory_info = detector.get_memory_info()
        memory_panel = Panel(
            f"💾 [bold]Memory Status[/bold]\n"
            f"Available: [green]{memory_info['available_gb']:.1f} GB[/green] / {memory_info['total_gb']:.1f} GB\n"
            f"Usage: [{'red' if memory_info['percent_used'] > 80 else 'yellow' if memory_info['percent_used'] > 60 else 'green'}]{memory_info['percent_used']:.1f}%[/]\n"
            f"Free: [green]{memory_info['total_gb'] - memory_info['used_gb']:.1f} GB[/green]",
            title="Memory Information"
        )
        console.print(memory_panel)
        
        # GPU memory if available
        if hardware.gpu_available and any(key.startswith('gpu_') for key in memory_info.keys()):
            gpu_memory_info = []
            for i in range(hardware.gpu_count):
                if f'gpu_{i}_total_gb' in memory_info:
                    total = memory_info[f'gpu_{i}_total_gb']
                    free = memory_info[f'gpu_{i}_free_gb']
                    used_pct = ((total - free) / total * 100) if total > 0 else 0
                    gpu_memory_info.append(f"GPU {i}: {free:.1f}GB free / {total:.1f}GB ({used_pct:.1f}% used)")
            
            if gpu_memory_info:
                gpu_panel = Panel(
                    "\n".join(gpu_memory_info),
                    title="GPU Memory Status"
                )
                console.print(gpu_panel)
        
        # System health indicators
        health_indicators = []
        
        if memory_info['percent_used'] > 90:
            health_indicators.append("⚠️  High memory usage - consider reducing workers")
        elif memory_info['percent_used'] < 50:
            health_indicators.append("✅ Good memory availability")
        
        if hardware.gpu_available:
            health_indicators.append("✅ GPU acceleration available")
        else:
            health_indicators.append("ℹ️  CPU-only processing (consider GPU for better performance)")
        
        if hardware.optimal_workers >= 4:
            health_indicators.append("✅ Good parallel processing capability")
        else:
            health_indicators.append("ℹ️  Limited parallel processing (consider more cores)")
        
        if health_indicators:
            health_panel = Panel(
                "\n".join(health_indicators),
                title="System Health",
                border_style="green"
            )
            console.print(health_panel)
        
    except Exception as e:
        if quiet:
            click.echo(f"Error: {e}")
        else:
            console.print(f"❌ [red]Failed to get system status: {e}[/red]")
        raise


def show_job_status(quiet: bool = False):
    """Display active job status (placeholder for future worker implementation)."""
    console = Console()
    
    if quiet:
        click.echo("No active jobs")
        return
    
    # Try to query Celery/Redis for simple stats
    console.print("📋 [bold blue]Job Status[/bold blue]")

    try:
        from ...workers.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=0.5)
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        reserved = inspect.reserved() or {}

        def count_tasks(mapping):
            total = 0
            for _, tasks in (mapping or {}).items():
                total += len(tasks or [])
            return total

        job_table = Table(title="Transcription Queue Overview")
        job_table.add_column("Metric", style="cyan")
        job_table.add_column("Count", style="green")

        job_table.add_row("Active", str(count_tasks(active)))
        job_table.add_row("Scheduled", str(count_tasks(scheduled)))
        job_table.add_row("Reserved", str(count_tasks(reserved)))

        console.print(job_table)

        if not (active or scheduled or reserved):
            console.print("ℹ️  [dim]No active workers or no jobs currently in the queue[/dim]")
    except Exception as e:
        console.print(f"⚠️  [yellow]Could not query workers: {e}[/yellow]")
        job_table = Table(title="Active Transcription Jobs")
        job_table.add_column("Job ID", style="cyan")
        job_table.add_column("File", style="green")
        job_table.add_column("Status", style="yellow")
        job_table.add_column("Progress", style="blue")
        job_table.add_column("Started", style="magenta")
        job_table.add_row("Unknown (workers unavailable)", "-", "-", "-", "-")
        console.print(job_table)


def show_worker_status(quiet: bool = False):
    """Display worker system status (placeholder for future implementation)."""
    console = Console()
    
    if quiet:
        click.echo("Workers: Not running")
        return
    
    console.print("👷 [bold blue]Worker Status[/bold blue]")
    
    worker_table = Table(title="Worker Processes")
    worker_table.add_column("Worker ID", style="cyan")
    worker_table.add_column("Status", style="green")
    worker_table.add_column("Current Task", style="yellow")
    worker_table.add_column("CPU %", style="blue")
    worker_table.add_column("Memory", style="magenta")
    
    # Placeholder data
    worker_table.add_row("No workers", "Stopped", "-", "-", "-")
    
    console.print(worker_table)
    
    console.print("ℹ️  [dim]Start workers with: talkgpt workers start[/dim]")