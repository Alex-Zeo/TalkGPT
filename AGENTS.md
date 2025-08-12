# TalkGPT - AI-Powered Transcription Pipeline

## Project Overview

TalkGPT is a modular, high-performance transcription pipeline built on OpenAI Whisper Fast Large. This system is designed to process audio and video files at scale with state-of-the-art accuracy and efficiency.

### Key Features

- **Cross-Platform Compatibility**: Automatic CPU/GPU detection and optimization
- **Intelligent Audio Processing**: Smart chunking with silence detection and speed optimization
- **Advanced Analytics**: Speaker overlap detection and transcription uncertainty flagging
- **Scalable Architecture**: Dynamic concurrency management with Celery integration
- **Production-Ready Logging**: Comprehensive terminal and per-file logging system
- **Flexible Output**: Timestamped transcriptions in multiple formats (SRT, JSON, CSV)

### Performance Characteristics

- **Speed**: 60% of real-time processing (configurable 1.5x-3x speed multiplier)
- **Accuracy**: State-of-the-art Whisper Large-v3 with uncertainty detection
- **Scalability**: Parallel processing with automatic resource optimization
- **Reliability**: Robust error handling and comprehensive logging

---

## System Architecture

### Core Components

| Component | Purpose | Key Technologies |
|-----------|---------|------------------|
| **Resource Detection** | Hardware optimization and capability assessment | PyTorch CUDA, MPS detection |
| **File Processing** | Batch discovery, format standardization, speed optimization | FFmpeg, Pydub, Librosa |
| **Smart Chunking** | Silence-based segmentation with overlap handling | Voice Activity Detection (VAD) |
| **Transcription Engine** | Fast Whisper processing with confidence scoring | faster-whisper, CTranslate2 |
| **Concurrency Manager** | Parallel processing coordination | Celery, multiprocessing |
| **Analytics Engine** | Speaker diarization and uncertainty detection | pyannote.audio |
| **Output Generator** | Multi-format timestamped transcript creation | SRT, JSON, CSV formats |
| **Logging System** | Comprehensive monitoring and diagnostics | Python logging, Rich |
| **CLI Interface** | Command-line interface for direct pipeline control | Click, argparse, Rich |
| **MCP Server** | Model Context Protocol for AI agent integration | FastAPI, JSON-RPC, WebSockets |

### File Structure

```
TalkGPT/
├── AGENTS.md                 # Main project documentation and architecture
├── src/                      # Source code directory
│   ├── core/                 # Core pipeline components
│   │   ├── AGENTS_core.md           # Core module agent documentation
│   │   ├── __init__.py
│   │   ├── resource_detector.py     # Hardware detection and optimization
│   │   ├── file_processor.py        # Audio/video preprocessing
│   │   ├── chunker.py               # Smart audio segmentation
│   │   ├── transcriber.py           # Whisper transcription engine
│   │   └── output_generator.py      # Multi-format output creation
│   ├── analytics/            # Advanced analysis modules
│   │   ├── AGENTS_analytics.md      # Analytics module agent documentation
│   │   ├── __init__.py
│   │   ├── speaker_analyzer.py      # Diarization and overlap detection
│   │   └── uncertainty_detector.py  # Confidence scoring and flagging
│   ├── utils/                # Utility modules
│   │   ├── AGENTS_utils.md          # Utils module agent documentation
│   │   ├── __init__.py
│   │   ├── logger.py                # Logging configuration
│   │   ├── config.py                # Configuration management
│   │   └── validators.py            # Input validation utilities
│   ├── workers/              # Concurrency and task management
│   │   ├── AGENTS_workers.md        # Workers module agent documentation
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery configuration
│   │   └── task_manager.py          # Task coordination
│   ├── cli/                  # Command Line Interface
│   │   ├── AGENTS_cli.md            # CLI module agent documentation
│   │   ├── __init__.py
│   │   ├── main.py                  # Main CLI entry point
│   │   ├── commands/                # CLI command modules
│   │   │   ├── __init__.py
│   │   │   ├── transcribe.py        # Transcription commands
│   │   │   ├── batch.py             # Batch processing commands
│   │   │   ├── config.py            # Configuration commands
│   │   │   └── status.py            # Status and monitoring commands
│   │   └── parsers/                 # Argument parsers
│   │       ├── __init__.py
│   │       ├── base.py              # Base parser functionality
│   │       └── validators.py        # Argument validation
│   └── mcp/                  # Model Context Protocol Support
│       ├── AGENTS_mcp.md            # MCP module agent documentation
│       ├── __init__.py
│       ├── server.py                # MCP server implementation
│       ├── handlers/                # MCP request handlers
│       │   ├── __init__.py
│       │   ├── transcription.py     # Transcription request handlers
│       │   ├── pipeline.py          # Pipeline management handlers
│       │   └── status.py            # Status query handlers
│       ├── tools/                   # MCP tool definitions
│       │   ├── __init__.py
│       │   ├── transcribe_tool.py   # Transcription tool
│       │   ├── batch_tool.py        # Batch processing tool
│       │   └── config_tool.py       # Configuration tool
│       └── schemas/                 # MCP schema definitions
│           ├── __init__.py
│           ├── requests.py          # Request schemas
│           └── responses.py         # Response schemas
├── config/                   # Configuration files
│   ├── default.yaml          # Default configuration
│   ├── production.yaml       # Production settings
│   ├── cli.yaml              # CLI-specific configuration
│   └── mcp.yaml              # MCP server configuration
├── tests/                    # Test suite
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   ├── cli/                  # CLI-specific tests
│   ├── mcp/                  # MCP-specific tests
│   └── fixtures/             # Test data
├── scripts/                  # Utility scripts
│   ├── setup_environment.py  # Environment setup
│   ├── benchmark.py          # Performance benchmarking
│   ├── generate_docs.py      # Documentation generation from module AGENTS files
│   └── start_mcp_server.py   # MCP server startup script
├── docs/                     # Documentation
│   ├── api/                  # API documentation
│   ├── deployment/           # Deployment guides
│   ├── cli/                  # CLI usage documentation
│   ├── mcp/                  # MCP integration documentation
│   └── examples/             # Usage examples
├── requirements.txt          # Python dependencies
├── requirements-cli.txt      # CLI-specific dependencies
├── requirements-mcp.txt      # MCP-specific dependencies
├── docker-compose.yml        # Container orchestration
├── Dockerfile               # Container definition
├── Dockerfile.mcp           # MCP server container
└── README.md                # Quick start guide
```

---

## Technical Implementation Plan

### 1. System Resource Detection (Cross-Platform)

First, the script should **inspect the host system’s specs** to optimize subsequent steps:

* **Hardware Check:** Detect available hardware resources, including number of CPU cores, total RAM, and GPU presence (e.g., using `torch.cuda.is_available()` for NVIDIA GPUs or checking Apple Silicon/MPS on macOS). This ensures the script can choose the optimal processing mode (CPU vs GPU) and concurrency level.
* **GPU vs CPU Mode:** If a compatible GPU is found, prefer loading the Whisper model on GPU for speed. If multiple GPUs are present, note their count and memory to potentially distribute workloads. On CPU-only systems, consider using performance tweaks (like PyTorch CPU threading or quantization) to maximize speed.
* **Cross-Platform Considerations:** Use libraries and commands that work on Windows, macOS, and Linux. For example, avoid shell-specific commands; use Python’s standard library (`os`, `pathlib`) for file operations and system queries. Ensure that any GPU checks also handle AMD GPUs or fallback appropriately (e.g., PyTorch MPS for Macs).
* **Resource-Based Decisions:** Store the detected specs in a config object. These will inform later modules – e.g., how many parallel transcription processes to run or whether to use GPU-accelerated decoding.

*(This module lays the groundwork for adaptive concurrency and hardware utilization in later steps.)*

### 2. Batch File Discovery & Preprocessing

Next, prepare the audio/video files for transcription by **finding and standardizing inputs**:

* **Folder Scanning:** Recursively search the given input folder for audio/video files. Support common extensions (e.g., `.wav`, `.mp3`, `.m4a`, `.flac`, `.mp4`, `.mkv`, etc.). Build a list of file paths to process.
* **Format Standardization:** For each file, convert it to a *consistent audio format* (if not already). Use `ffmpeg` or similar to decode video to audio and resample as needed. For example, convert to a **16 kHz mono WAV** – Whisper’s default – to ensure compatibility. This step can also normalize audio volume.
* **Speed Augmentation:** As part of conversion, apply an **audio speed-up filter** to reduce length without significant quality loss. Best practice is to increase playback speed (time-compress the audio) by a factor (e.g., 1.5× by default, i.e. 150% speed) to shorten transcription time. Studies have shown that speeding audio 2–3× yields “almost no drop in transcription quality” while dramatically reducing processing time. For instance, using FFmpeg’s `atempo` filter at 1.6× (about 60% of original duration) can be the default, with this factor made adjustable.
* **Output of Preprocessing:** The result is a set of optimized WAV files (with unified sample rate, channels, and possibly accelerated playback). By standardizing upfront, subsequent transcription can be handled uniformly for all inputs.

*Speeding up audio (2–3×) before transcription saves time “with almost no drop in transcription quality”*.

### 3. Smart Chunking with Silence Detection

To handle long files efficiently and accurately, implement **audio chunking** with silence-based boundaries:

* **Reason for Chunking:** Whisper’s models process audio in roughly 30-second “windows” internally. Very long audio can be split into manageable segments to reduce memory usage and enable parallelism. However, naive splitting can cut words or context, harming accuracy.
* **Silence Detection:** Use a Voice Activity Detection (VAD) or silence-detection algorithm to identify natural pause points. For example, utilize `pydub` or `librosa` to find intervals of low volume longer than a threshold (e.g. >0.5 seconds). Aim to split at these quiet gaps **between words/sentences** so that segments start and end in silence.
* **Max Segment Length:** Define an upper length (e.g. 5–10 minutes per chunk) to avoid extremely large segments. Within that window, prefer the last silence before the limit as the split point. This ensures no segment exceeds what the system can handle, while avoiding mid-phrase cuts.
* **Overlap Strategy:** To further avoid chopping words, include a slight **overlap** between consecutive chunks. For instance, if using 30s chunks, a 5s overlap is effective. This means the end of chunk N and beginning of chunk N+1 share a few seconds of audio, helping Whisper “hear” context at boundaries. The Hugging Face ASR pipeline uses \~1/6 of chunk length as overlap by default for seamless boundaries.
* **Silence Removal (Optional):** For pure speed optimization, consider cutting out long stretches of silence entirely. Removing silence can *both* speed up processing and improve transcription quality (it prevents the model from hallucinating speech in silence). For example, an `ffmpeg` `silenceremove` filter can trim quiet sections, which one user reported reduced a recording to 2/3 its length and **improved accuracy**. Ensure a minimal gap remains so words don’t slur.
* **Summary:** This module produces chunked audio segments for each file, split cleanly at silence (with minor overlaps). It maximizes accuracy by aligning splits with natural pauses and maintaining context between chunks.

*Using a small overlap (e.g. \~5s on a 30s chunk) prevents cutting words and yields accurate transcripts at segment boundaries.*
*Removing silent pauses shortens processing time and “increases a lot the quality of the transcription, as silence can mean hallucinations.”*

### 4. Optimized Transcription Playback Speed

Leverage **playback speed adjustments** to further accelerate transcription:

* **Default Speed Setting:** By default, use \~1.5× playback speed for transcription. This corresponds to processing audio at \~60% of real-time (e.g., a 10-minute recording plays in 6 minutes). As noted earlier, significant speed-ups (2–3×) have minimal impact on accuracy. Our conservative default (1.5×) balances speed and risk, and can be tuned if needed.
* **Adjustable Configuration:** Expose a setting (via config file or CLI argument) to adjust the speed factor. For example, allow values from 1.0 (no speed-up) up to, say, 3.0 for maximum acceleration. Users with high-end hardware or non-critical accuracy can experiment with higher values.
* **Mechanism:** The speed-up can be achieved by time-stretching audio without altering pitch. Using FFmpeg: `ffmpeg -i input.wav -filter:a "atempo=1.5" output_fast.wav`. Ensure that the Whisper model still receives audio at the expected sample rate (e.g., 16kHz) – the speed-up shortens duration but retains intelligibility.
* **GPU Utilization:** If running on GPU, faster audio means fewer total samples to process, improving throughput. If on CPU, this reduces compute time proportionally. Always monitor that extreme speeds don’t degrade transcription significantly.
* **Playback Speed Best Practice:** This trick essentially “makes the minutes shorter” for Whisper. As one experimenter put it: speeding audio by 2–3× led to **fewer tokens and faster transcriptions with virtually no quality drop**. Our default of 1.5× is a safe starting point aligned with that finding.
* **Note:** Combine this with silence trimming – first remove long silences, then speed up the remaining speech. This compound approach yields a big efficiency gain.

*(By processing audio faster than real-time, we cut down transcription time and cost dramatically while maintaining accuracy.)*

### 5. Concurrency and Parallel Processing

Implement a **concurrency strategy** to transcribe multiple files (or chunks) in parallel, guided by system specs:

* **Determine Optimal Workers:** Based on the earlier system check, decide how many concurrent transcription processes to run. For CPU-only systems, a good rule is to use about 50–70% of CPU cores for heavy jobs to avoid contention (e.g., on 8 cores, use \~4–6 parallel workers by default). For GPU, typically run **one large model per GPU** to maximize utilization (Whisper-large is heavy). If multiple GPUs are available, schedule one worker per GPU.
* **Celery or Multiprocessing:** For a robust solution, consider using **Celery** with a worker pool. Celery can manage a queue of audio chunks as tasks, allowing flexible concurrency and distribution. Each Celery worker (or process) would load the Whisper model (ideally once, kept in memory) and transcribe assigned chunks. This decouples the producer (file scanner) from the consumers (transcribers), and can scale out if needed.

  * *Alternative:* In a simpler script, Python’s `concurrent.futures.ProcessPoolExecutor` or the `multiprocessing` module can spawn processes to handle chunks in parallel. This avoids external dependencies but runs within a single machine.
* **Avoid GIL Bottlenecks:** Whisper’s heavy lifting occurs in deep learning libraries (PyTorch), which release the GIL, so multi-threading could, in theory, be used. However, due to Python GIL and model global state, **multi-process concurrency** is safer. Each process or worker gets its own model instance. (Attempting to have threads share one model often leads to garbled outputs.)
* **Memory Consideration:** Loading Whisper-large multiple times is memory-intensive (each instance \~>2GB VRAM for GPU or significant RAM for CPU). Thus, limit the number of concurrent processes such that the system has enough memory for all. On a 16GB GPU, for example, two large models might fit (8GB each). On CPU, ensure total processes \* model RAM < total system RAM.
* **Scaling Option:** If needed, Celery can distribute across machines or you could use a cluster, but assume local concurrency unless otherwise specified.
* **Throughput Control:** As a default, aim to use \~60% of available throughput (e.g., leave some cores idle or one GPU free) to avoid saturating system resources – this helps keep the system responsive. This default concurrency level can be configurable (“–max-workers” flag to override).
* **Outcome:** With concurrency, multiple audio chunks or files will be processed in parallel, drastically speeding up batch transcription. The script should gather these results and later reassemble them in order.

*Attempting to use the same Whisper model simultaneously in multiple processes can fail (“!!!” output), so run separate model instances per worker for reliable parallelism.*

### 6. Logging and Monitoring

Integrate a robust **logging** mechanism to track the transcription process, both in the console and in log files:

* **Python Logging Setup:** Use the built-in `logging` module to configure a logger early on. Set an appropriate log level (INFO for regular operation, DEBUG for verbose diagnostics). Use a consistent format including timestamps, module name, and log level for clarity.
* **Console Logs:** Attach a `StreamHandler` for console output. This can show high-level progress – e.g., “Starting transcription of file X”, “Completed chunk 3/5 of file Y”, warnings about any issues, etc. Keep console logs concise and user-friendly.
* **File per Input:** For detailed logs, create a separate log file for each input file (or each chunk, if needed). Best practice is to name the log after the audio filename, e.g., `meeting1.wav.log`. Attach a `FileHandler` that writes all INFO/WARN/ERROR messages related to that file. This way, users can inspect logs for each transcription result individually.
* **Thread/Process Safety:** When using concurrency, ensure logs from different workers don’t intermix confusingly. Options include:

  * Each worker/process gets its own logger (with its own file handler). For example, include the process ID or file name in the logger name.
  * Use a logging **QueueHandler/QueueListener** pattern to synchronize logs from multiple processes to a single file if needed, but per-file logs simplify this.
* **Log Content:**

  * INFO logs: start/finish of transcribing a file or chunk, detection of language (Whisper can auto-detect language), any speed-ups applied, etc.
  * WARN logs: if a chunk had to be split in a less optimal way (e.g., no silence found, so a mid-sentence split occurred), or if audio had low volume segments, etc.
  * ERROR logs: any exceptions (e.g., file decode failures).
* **Progress Monitoring:** Consider a simple progress bar or periodic log updates for long files (“Processed 10min of 60min…”).
* **Cleanup:** Ensure that each log file is closed properly when its transcription is done. Possibly summarize at the end: e.g., “Transcribed 5 files (total 2 hours audio) in 8 minutes. See logs for details.”
* **Terminal vs File Detail:** The terminal might just say “File X done, output saved to … (see X.log for processing details)”. Detailed per-file logs reside alongside outputs.

*(Good logging will make it easier to debug and audit transcriptions, especially when running many files in parallel.)*

### 7. Speaker Overlap Detection & Flagging

Flag sections of transcript where **multiple speakers overlap**, using state-of-the-art techniques:

* **Why Overlap Matters:** Overlapping speech (two people talking at once) often leads to jumbled transcription or missed words. Marking these regions alerts the user that those transcript segments may be less reliable or need special attention.
* **Diarization Models:** Employ a **speaker diarization** pipeline to analyze the audio for speaker segments and overlaps. The SOTA approach is to use dedicated models (e.g., **pyannote.audio** or NVIDIA NeMo) that can detect **overlapped speech** with high accuracy. These models output time-stamped segments for each speaker, including when two speakers talk simultaneously.
* **Integration:** After (or during) transcription, run the diarization model on the audio (could be on the original full audio or on chunks). Focus on retrieving **overlap regions** – e.g., pyannote’s *overlapped speech detection* can provide time intervals where overlap occurs.
* **Flagging Mechanism:** Once overlaps are identified (time start/end), map those times to the transcript. For example:

  * If using the transcript segments with timestamps, check which transcript lines fall into an overlapping interval.
  * Mark these lines (or specific words) with a special tag, e.g., `[⚠ overlapping speech]` or highlight them in the output.
* **Output Representation:** In a text transcript, you might insert a marker like `<<Overlap>>` at the beginning of a segment that had overlap, or color-code it if the output format allows. In subtitles (SRT/VTT), perhaps add a note in parentheses.
* **Performance:** Running a full diarization (especially a neural model) is computationally heavy. If real-time speed is crucial, consider simplifying: e.g., a lightweight heuristic like sudden audio energy spikes might guess overlap, but for SOTA accuracy, the neural diarization is preferred.
* **State of the Art:** Modern diarization can reach near human-level accuracy in labeling speakers. Pyannote, for instance, provides **pretrained pipelines** for speaker attribution with *state-of-the-art performance* on benchmarks. We leverage these to ensure overlaps are detected reliably.
* **Cross-Validation:** Optionally, use the Whisper transcript itself to assist (if two voices are transcribed into one, punctuation might be odd or there might be an `[inaudible]` tag mid-sentence; those could hint at overlap).
* **Result:** The transcript will have clear indicators for regions with overlapping dialogue, guiding users to treat those sections with caution or manually review the audio.

*Pyannote.audio provides state-of-the-art pretrained models for speaker diarization.*
*Pyannote’s toolkit includes neural modules for overlapped speech detection to pinpoint when speakers talk simultaneously.*

### 8. Uncertainty Detection & Flagging

Identify and flag transcript sections where Whisper was **uncertain** about the transcription:

* **Rationale:** Whisper (and ASR models in general) sometimes produce low-confidence output – e.g., garbled text or incorrect words – especially with noise or unclear speech. Highlighting such segments helps users know where the transcript might be wrong.
* **Confidence Measures:** Utilize Whisper’s internal confidence metrics. Whisper doesn’t directly output a confidence score per word, but it does compute an **average log probability** for each predicted text segment. This is effectively a proxy for confidence – higher average log-prob (closer to 0) means the model is more sure, while very negative values indicate uncertainty. The Whisper paper uses a threshold around -1.0 for average log-probability to decide if a segment is low-confidence.
* **Implementation:** After transcription, for each segment (or each word if using word timestamps), retrieve the model’s confidence:

  * If using the open-source Whisper code, the `transcribe()` result includes `segments` with an `avg_logprob`. Compare this to a threshold (e.g., -1.0). Segments below the threshold can be flagged.
  * Alternatively, if using `whisper.cpp` or other implementations, they may provide token-level probabilities or a confidence coloring feature (some forks output words color-coded by confidence).
* **Flagging Criteria:** Define what counts as “high uncertainty.” This could be:

  * Average log-probability < -1.0 (as in the default heuristic).
  * Or the presence of tokens like “\[?]” or `<|inaudible|>` in the text (which Whisper uses for uncertain audio).
  * Or a very high compression ratio (Whisper’s other heuristic for potential hallucinations) – though that usually flags repetitive output.
* **Highlighting in Transcript:** Mark low-confidence segments with a special notation, such as appending `(?)` or coloring the text. For example: *"It was [unintelligible](?) at the time"* to show the model isn’t sure. If outputting to a structured format (JSON, or an app UI), include a confidence score for each segment.
* **Improving Confidence (optional):** For critical use-cases, one might re-run low-confidence segments through a different model or with a different decoding strategy (e.g., Whisper has a **temperature fallback** that retries decoding if confidence is low). Our plan will at least flag them; further improvement can be an extension.
* **Research Edge:** Note that research is ongoing to get word-level confidence from Whisper, including fine-tuning approaches to predict confidence. Our implementation leverages existing heuristics as a practical solution.
* **Outcome:** The final transcript will visibly mark parts that are likely error-prone, guiding users or downstream processes to review those parts of the audio manually.

*Whisper uses the average log probability of decoded tokens as “a confidence measure of the model’s predictions,” with the authors using -1.0 as a default threshold for low confidence.*

### 9. Timestamped Transcript Output

Produce a **timestamped transcript**, with each line (or sentence) labeled with its time in the audio:

* **Segment Timestamps:** Leverage Whisper’s output, which includes start and end timestamps for each transcribed segment. The `model.transcribe()` function returns a list of segments with `start` and `end` times. Each segment typically corresponds to a phrase or sentence.
* **Granularity:** By default, Whisper’s segments are a suitable granularity (often a sentence or clause). We can use these as “rows” in the output. If finer detail is needed, Whisper’s newer options allow **word-level timestamps** (by setting `word_timestamps=True` in recent versions), enabling splitting by word or sentence punctuation. For most cases, segment-level is sufficient.
* **Formatting:** Choose an output format that preserves timestamps:

  * **Subtitle files (SRT/VTT):** This is a convenient option. We can write each segment as a subtitle cue with its start–end time and text. This makes it easy to read along with the audio/video.
  * **CSV/JSON:** Alternatively, output a table (CSV) or JSON where each entry has `start_time`, `end_time`, `text`, and any flags (like speaker or uncertainty flags from steps 7 and 8). This is useful for programmatic consumption.
  * **Plain Text with Timestamps:** e.g., `[00:03.500 --> 00:07.200] Hello, how are you?`
* **Speaker Labels:** If speaker diarization was performed, incorporate speaker labels per segment (e.g., prefix each line with Speaker A/B if known) and note overlaps as discussed.
* **Post-processing Sentences:** If Whisper segments are too short or mid-sentence (sometimes it might split or run-on sentences), consider merging or splitting segments based on punctuation for a cleaner “one sentence per line” output. Ensure the timestamp reflects the beginning of that sentence.
* **Verification:** Double-check that the ordering of segments by time aligns with the original audio. Our earlier chunking step maintained chronological order; now we just need to output accordingly. If chunks were processed out of order (due to parallelism), make sure to sort the final segments by start time before output.
* **Sample Output (SRT):**

```srt
1
00:00:00,000 --> 00:00:05,200
Speaker 0: Hello, my name is Alice.

2
00:00:05,200 --> 00:00:07,800
Speaker 1: Hi Alice, I'm Bob. <<Overlap>> (uncertain)
```

In the above, `<<Overlap>>` indicates overlapping speech and “(uncertain)” marks a low-confidence segment.

* **User Confirmation:** Finally, print or log where the transcript is saved. If multiple formats are saved (e.g., .txt and .srt), list them.

*Using the Whisper API, `result["segments"]` provides timestamps for each segment of transcribed text.*
*Newer Whisper versions support `word_timestamps=True` to get word-level time markers, which can be used to build sentence-level timestamps if needed.*

---

## Implementation Summary

This technical plan creates a highly optimized Whisper transcription pipeline that:

- **Adapts to Hardware**: Automatically detects and optimizes for available CPU/GPU resources
- **Preprocesses Intelligently**: Standardizes formats, applies speed optimization, and removes silence
- **Chunks Smartly**: Segments audio at natural pause points with overlap handling
- **Processes in Parallel**: Scales transcription across multiple workers for maximum throughput
- **Monitors Comprehensively**: Provides detailed logging for debugging and auditing
- **Analyzes Advanced Features**: Detects speaker overlap and transcription uncertainty
- **Outputs Flexibly**: Generates timestamped transcripts in multiple formats

The modular architecture ensures maintainability, scalability, and adaptability to different project requirements while following state-of-the-art practices for maximum speed and accuracy.

---

## Module Documentation Strategy

### AGENTS{module}.md Architecture

Each module maintains its own `AGENTS_{module}.md` file that serves as the definitive documentation for AI agents and developers working with that specific module. This distributed documentation approach provides several key benefits:

**Documentation Hierarchy**:
- **Main AGENTS.md**: High-level architecture, system overview, and integration points
- **Module AGENTS_{module}.md**: Detailed module-specific documentation, APIs, and implementation details
- **Auto-sync**: Module documentation feeds into main documentation through automated generation

### Module Documentation Standards

Each `AGENTS_{module}.md` file follows a consistent structure:

```markdown
# {Module Name} - Agent Documentation

## Module Overview
- Purpose and responsibilities
- Key components and their roles
- Integration points with other modules

## API Reference
- Public functions and classes
- Input/output specifications
- Error handling patterns

## Configuration
- Module-specific configuration options
- Environment variables
- Default settings

## Usage Examples
- Common use cases
- Code snippets
- Integration patterns

## Implementation Details
- Internal architecture
- Data flow
- Performance considerations

## Testing
- Test coverage
- Mock data requirements
- Integration test patterns

## Troubleshooting
- Common issues and solutions
- Debug logging patterns
- Performance tuning
```

### Documentation Synchronization

**Automated Generation**: The `scripts/generate_docs.py` script aggregates module documentation into the main AGENTS.md file, ensuring consistency and reducing maintenance overhead.

**Update Workflow**:
1. Developers update module-specific `AGENTS_{module}.md` files
2. CI/CD pipeline runs documentation generation
3. Main AGENTS.md file is updated with module changes
4. Version control tracks both module and main documentation changes

---

## Command Line Interface (CLI)

### CLI Architecture

The TalkGPT CLI provides a simple, intuitive interface for all transcription pipeline operations. Built with modern CLI best practices, it supports both interactive and batch processing modes.

### Command Structure

```bash
talkgpt [GLOBAL_OPTIONS] <command> [COMMAND_OPTIONS] [ARGUMENTS]
```

### Core Commands

#### 1. Transcription Commands

```bash
# Single file transcription
talkgpt transcribe input.wav --output results/ --format srt,json

# Batch folder processing
talkgpt batch /path/to/audio/folder --output /path/to/results --workers 4

# Real-time transcription (streaming)
talkgpt stream --input-device microphone --output-format live
```

#### 2. Configuration Management

```bash
# View current configuration
talkgpt config show

# Set configuration values
talkgpt config set processing.speed_multiplier 1.75
talkgpt config set transcription.model_size large-v3

# Reset to defaults
talkgpt config reset

# Validate configuration
talkgpt config validate
```

#### 3. System Management

```bash
# Check system capabilities
talkgpt status system

# Monitor active transcriptions
talkgpt status jobs

# View processing queue
talkgpt status queue

# Performance benchmarking
talkgpt benchmark --duration 60 --sample-files test_audio/
```

#### 4. Advanced Operations

```bash
# Speaker analysis
talkgpt analyze speakers input.wav --output speaker_report.json

# Quality assessment
talkgpt analyze quality input.wav --confidence-threshold 0.8

# Pipeline debugging
talkgpt debug pipeline --input input.wav --verbose
```

### Global Options

```bash
--config PATH          # Custom configuration file
--log-level LEVEL      # Logging verbosity (DEBUG, INFO, WARN, ERROR)
--quiet               # Suppress console output
--output-format FORMAT # Default output format (srt, json, txt, csv)
--workers N           # Override worker count
--gpu / --cpu         # Force processing mode
--profile             # Enable performance profiling
```

### CLI Configuration

The CLI uses a hierarchical configuration system:

1. **Command-line arguments** (highest priority)
2. **Environment variables** (TALKGPT_*)
3. **User config file** (~/.talkgpt/config.yaml)
4. **Project config file** (./config/cli.yaml)
5. **Default settings** (lowest priority)

### CLI Examples

```bash
# Basic transcription with custom settings
talkgpt transcribe meeting.mp4 \
  --output ./transcripts/ \
  --format srt,json \
  --speed-multiplier 1.8 \
  --workers 6

# Batch processing with speaker analysis
talkgpt batch ./audio_files/ \
  --output ./results/ \
  --analyze-speakers \
  --confidence-threshold 0.9 \
  --log-level DEBUG

# Configuration and monitoring
talkgpt config set processing.chunk_size 30
talkgpt status system
talkgpt benchmark --quick
```

---

## Model Context Protocol (MCP) Support

### MCP Architecture

The Model Context Protocol integration enables AI agents to interact with the TalkGPT pipeline programmatically. This allows for sophisticated automation, integration with AI workflows, and seamless operation within agent-driven environments.

### MCP Server Implementation

**Server Components**:
- **MCP Server**: Core protocol implementation handling agent requests
- **Tool Registry**: Available tools and their capabilities
- **Request Handlers**: Process specific operation types
- **Schema Validation**: Ensure request/response integrity

### Available MCP Tools

#### 1. Transcription Tools

```json
{
  "name": "transcribe_audio",
  "description": "Transcribe audio/video files with advanced options",
  "inputSchema": {
    "type": "object",
    "properties": {
      "input_path": {"type": "string", "description": "Path to audio/video file"},
      "output_format": {"type": "array", "items": {"enum": ["srt", "json", "txt", "csv"]}},
      "speed_multiplier": {"type": "number", "minimum": 1.0, "maximum": 3.0},
      "analyze_speakers": {"type": "boolean"},
      "confidence_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0}
    },
    "required": ["input_path"]
  }
}
```

#### 2. Batch Processing Tools

```json
{
  "name": "batch_transcribe",
  "description": "Process multiple audio files in batch",
  "inputSchema": {
    "type": "object",
    "properties": {
      "input_directory": {"type": "string"},
      "output_directory": {"type": "string"},
      "file_patterns": {"type": "array", "items": {"type": "string"}},
      "max_workers": {"type": "integer", "minimum": 1, "maximum": 32},
      "processing_options": {"type": "object"}
    },
    "required": ["input_directory", "output_directory"]
  }
}
```

#### 3. Pipeline Management Tools

```json
{
  "name": "pipeline_status",
  "description": "Get current pipeline status and metrics",
  "inputSchema": {
    "type": "object",
    "properties": {
      "include_queue": {"type": "boolean"},
      "include_workers": {"type": "boolean"},
      "include_system": {"type": "boolean"}
    }
  }
}
```

#### 4. Configuration Tools

```json
{
  "name": "configure_pipeline",
  "description": "Update pipeline configuration",
  "inputSchema": {
    "type": "object",
    "properties": {
      "config_updates": {"type": "object"},
      "validate_only": {"type": "boolean"},
      "persist": {"type": "boolean"}
    },
    "required": ["config_updates"]
  }
}
```

### MCP Integration Patterns

#### Agent Workflow Example

```python
# AI Agent using MCP to process audio files
async def process_meeting_recordings(agent, audio_files):
    """Process meeting recordings with speaker analysis"""
    
    results = []
    for audio_file in audio_files:
        # Transcribe with speaker analysis
        response = await agent.call_tool("transcribe_audio", {
            "input_path": audio_file,
            "output_format": ["srt", "json"],
            "analyze_speakers": True,
            "confidence_threshold": 0.85
        })
        
        # Extract key insights
        insights = await agent.call_tool("analyze_transcript", {
            "transcript_path": response["output_files"]["json"],
            "extract_action_items": True,
            "summarize_speakers": True
        })
        
        results.append({
            "file": audio_file,
            "transcript": response,
            "insights": insights
        })
    
    return results
```

#### Automation Integration

```yaml
# GitHub Actions workflow using MCP
name: Process Audio Files
on:
  push:
    paths: ['audio/**/*.mp3', 'audio/**/*.wav']

jobs:
  transcribe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup TalkGPT MCP
        run: |
          pip install talkgpt[mcp]
          talkgpt-mcp start --config production
      - name: Process Changed Files
        run: |
          # Agent script that uses MCP to process new audio files
          python scripts/auto_transcribe.py --mcp-endpoint localhost:8000
```

### MCP Server Configuration

```yaml
# config/mcp.yaml
server:
  host: "0.0.0.0"
  port: 8000
  max_connections: 100
  request_timeout: 300

tools:
  transcribe_audio:
    enabled: true
    max_file_size: "500MB"
    supported_formats: ["wav", "mp3", "m4a", "flac", "mp4", "mkv"]
  
  batch_transcribe:
    enabled: true
    max_batch_size: 50
    concurrent_jobs: 4

security:
  api_key_required: true
  rate_limiting:
    requests_per_minute: 60
    burst_size: 10

logging:
  level: "INFO"
  format: "json"
  file: "logs/mcp_server.log"
```

### MCP Deployment

#### Local Development
```bash
# Start MCP server for development
talkgpt-mcp start --config config/mcp.yaml --dev

# Test MCP connection
talkgpt-mcp test --endpoint localhost:8000
```

#### Production Deployment
```bash
# Docker deployment
docker run -d \
  --name talkgpt-mcp \
  -p 8000:8000 \
  -v /data/audio:/data/audio \
  -v /data/config:/app/config \
  talkgpt:mcp

# Kubernetes deployment
kubectl apply -f k8s/mcp-deployment.yaml
```

---

## Dependencies and Environment

### Core Dependencies

The following table shows the minimum version pins required for reliable operation across CPU and GPU environments:

| Layer                     | Package                                                                      | **Pin**                                                                                                                                                                                                | Why it must be fixed                                                                                                                                              |
| ------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python runtime**        | python                                                                       | `>=3.9,<3.12`                                                                                                                                                                                          | `faster-whisper` officially supports “Python 3.9 or greater” but some compiled wheels (pyannote, CTranslate2 ≤ 4.5) are not yet published for 3.12+ ([GitHub][1]) |
| **Deep-learning stack**   | torch / torchaudio                                                           | **GPU CUDA 12.4 build**: `torch==2.4.0+cu124` `torchaudio==2.4.0+cu124`<br>**GPU CUDA 12.1 build**: `torch==2.2.1+cu121` `torchaudio==2.2.1+cu121`<br>**CPU-only**: `torch==2.4.0` `torchaudio==2.4.0` | Pins guarantee ABI compatibility with the corresponding CTranslate2 wheel (matrix below).                                                                         |
| **Inference engine**      | ctranslate2                                                                  | `>=4.5.0` **if CUDA ≥ 12.3**<br>`==4.4.0` **if CUDA 11/12.1**                                                                                                                                          | CT2 4.5 introduces cuDNN 9 support; older CUDA needs 4.4 or lower ([GitHub][1])                                                                                   |
| **Fast Whisper wrapper**  | faster-whisper                                                               | `==1.1.1` *(latest stable, 2025-01-01)*                                                                                                                                                                | Locks API that loads “large-v3” from HF; newer releases may change default VAD / batching logic.                                                                  |
| **Model weights**         | whisper-large-v3 (CT2)                                                       | `"Systran/faster-whisper-large-v3@refs/pr/1"`<br>*or a local conversion hash*                                                                                                                          | Using a fixed HF snapshot ID (or local commit hash) prevents silent weight updates ([Hugging Face][2])                                                            |
| **Silence / diarization** | pyannote.audio                                                               | `==3.2.*`                                                                                                                                                                                              | 3.x line matches Torch ≥ 2.0 API; later major versions may break overlap-detection pipelines.                                                                     |
| **Audio IO**              | ffmpeg-python                                                                | `==0.2.0` *(thin wrapper)*                                                                                                                                                                             | Keep in sync with Pydub / PyAV; newer betas occasionally pin incompatible PyAV versions.                                                                          |
| **Helpers**               | pydub `==0.25.1`, librosa `==0.10.2.post2`, rich `==13.7.0`, tqdm `==4.66.4` | Stable utility stack for chunking, logging and progress bars.                                                                                                                                          |                                                                                                                                                                   |

### PyTorch and CTranslate2 Compatibility Matrix

| CUDA toolkit on host | **Torch wheel**                                | **CT2 wheel**                              |
| -------------------- | ---------------------------------------------- | ------------------------------------------ |
| 12.4 – 12.6          | `torch--cu124` ≥ 2.4                           | `ctranslate2>=4.5.0`                       |
| 12.1                 | `torch--cu121` 2.2 – 2.3                       | `ctranslate2==4.4.0`                       |
| 11.x                 | *Not recommended* – stay on CUDA 12 or run CPU | `ctranslate2==3.24.0` (last CUDA 11 wheel) |

These pairs follow the tested matrix published by the CT2 maintainers ([GitHub][3]).

### Example Requirements File

```text
# ---- core runtime ----
python_version ~= "3.10"        # managed by your env manager

# ---- DL stack (GPU CUDA 12.4 example) ----
torch==2.4.0+cu124       --index-url https://download.pytorch.org/whl/cu124
torchaudio==2.4.0+cu124  --index-url https://download.pytorch.org/whl/cu124

# ---- Whisper fast ----
faster-whisper==1.1.1
ctranslate2==4.5.0

# ---- optional accuracy / metadata ----
pyannote.audio==3.2.1        # speaker overlap & diarization
pydub==0.25.1                # silence-based chunking
librosa==0.10.2.post2        # DSP helpers

# ---- utils ----
ffmpeg-python==0.2.0
rich==13.7.0
tqdm==4.66.4
```

*(Replace the CUDA wheel tags with `+cu121` or drop them entirely for CPU.)*

### Environment Configuration

```bash
# 1. Force exact HF snapshot when pulling weights
export HF_HUB_ENABLE_HF_TRANSFER=1
model_id="Systran/faster-whisper-large-v3@6b692f5"   # example commit hash

# 2. Reproducible threading
export OMP_NUM_THREADS=$(nproc)
export MKL_NUM_THREADS=$(nproc)

# 3. Avoid PyTorch auto-update pulls in Docker/CI
pip install --no-deps --require-hashes -r requirements.txt
```

### Installation Verification

```python
from faster_whisper import WhisperModel
model = WhisperModel("large-v3",
                     device="cuda" if torch.cuda.is_available() else "cpu",
                     compute_type="float16")   # or "int8_float16"
print(model.device, model.model_size)  # should print cuda / cpu + large-v3
```

If the script loads without wheel complaints and the first inference runs, your pins are correct.

### Dependency Management Best Practices

**Critical Requirements:**
- Pin **Python < 3.12** for maximum compatibility
- Use aligned **PyTorch × CTranslate2** wheel pairs from the compatibility matrix
- Lock **faster-whisper 1.1.1** for stable API behavior
- Freeze **whisper-large-v3** weights to a specific HuggingFace snapshot or local hash

Following these dependency pins ensures stable, reproducible deployments across different environments while maintaining optimal performance for the transcription pipeline.

---

## Getting Started

### Quick Setup

1. **Clone and Setup Environment**
   ```bash
   git clone <repository-url>
   cd TalkGPT
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   # Core pipeline
   pip install -r requirements.txt
   
   # CLI support (optional)
   pip install -r requirements-cli.txt
   
   # MCP support (optional)
   pip install -r requirements-mcp.txt
   ```

3. **Verify Installation**
   ```bash
   python scripts/setup_environment.py --verify
   
   # Test CLI (if installed)
   talkgpt --version
   talkgpt status system
   
   # Test MCP server (if installed)
   talkgpt-mcp test --quick
   ```

4. **Run First Transcription**
   
   **Using CLI:**
   ```bash
   talkgpt transcribe /path/to/audio/file.wav --output /path/to/results
   ```
   
   **Using Python API:**
   ```bash
   python -m src.main --input /path/to/audio/folder --output /path/to/results
   ```
   
   **Using MCP (for AI agents):**
   ```bash
   # Start MCP server
   talkgpt-mcp start --config config/mcp.yaml
   
   # Agent can now use MCP tools to transcribe
   ```

### Configuration

The system uses YAML configuration files in the `config/` directory:
- `default.yaml`: Base configuration with sensible defaults
- `production.yaml`: Optimized settings for production deployment
- `cli.yaml`: CLI-specific configuration and defaults
- `mcp.yaml`: MCP server configuration and tool settings

#### Core Configuration Options

**Processing Settings:**
- `processing.speed_multiplier`: Audio playback speed optimization (default: 1.75)
- `processing.max_workers`: Concurrency level (default: auto-detect)
- `processing.chunk_size`: Audio segment size in seconds (default: 30)
- `processing.overlap_duration`: Segment overlap in seconds (default: 5)

**Transcription Settings:**
- `transcription.model_size`: Whisper model variant (default: large-v3)
- `transcription.device`: Processing device (default: auto-detect)
- `transcription.compute_type`: Precision mode (default: float16)
- `transcription.language`: Target language (default: auto-detect)

**Output Settings:**
- `output.formats`: Output formats (default: [srt, json, txt])
- `output.include_timestamps`: Include detailed timestamps (default: true)
- `output.include_confidence`: Include confidence scores (default: true)
- `output.speaker_labels`: Include speaker identification (default: true)

#### CLI Configuration

The CLI supports configuration through multiple sources with the following priority:
1. Command-line arguments (highest)
2. Environment variables (TALKGPT_*)
3. User config (~/.talkgpt/config.yaml)
4. Project config (./config/cli.yaml)
5. System defaults (lowest)

#### MCP Configuration

MCP server settings control agent integration capabilities:
- `server.host`: Server bind address (default: 0.0.0.0)
- `server.port`: Server port (default: 8000)
- `server.max_connections`: Maximum concurrent connections (default: 100)
- `tools.enabled`: List of enabled MCP tools
- `security.api_key_required`: Require API key authentication (default: true)

---

## References

- [faster-whisper GitHub Repository][1]
- [Whisper Large-v3 Model Hub][2]
- [CTranslate2 CUDA Compatibility][3]

[1]: https://github.com/SYSTRAN/faster-whisper "GitHub - SYSTRAN/faster-whisper: Faster Whisper transcription with CTranslate2"
[2]: https://huggingface.co/Systran/faster-whisper-large-v3?utm_source=chatgpt.com "Systran/faster-whisper-large-v3 - Hugging Face"
[3]: https://github.com/SYSTRAN/faster-whisper/issues/1086?utm_source=chatgpt.com "CUDA compatibility with CTranslate2 · Issue #1086 - GitHub"

<!-- START:GENERATED -->
<!-- AGENTS_core.md -->

# Core Module - Agent Documentation

## Module Overview
- File preprocessing, smart chunking, transcription engine
- Integration points: used by CLI, MCP, analytics, and output layers

## API Reference
- `src/core/file_processor.py`
  - `class FileProcessor`
    - `scan_directory(directory, recursive=True, extensions=None) -> List[Path]`
    - `get_file_info(file_path) -> AudioFileInfo`
    - `process_file(input_path, output_dir, speed_multiplier=1.75, remove_silence=True, normalize=True, target_sample_rate=16000, target_channels=1) -> ProcessingResult`
- `src/core/chunker.py`
  - `class SmartChunker`
    - `chunk_audio(audio_path, output_dir=None, remove_silence=True) -> ChunkingResult`
    - `load_chunks_from_metadata(metadata_file) -> ChunkingResult`
- `src/core/transcriber.py`
  - `class WhisperTranscriber`
    - `transcribe_chunk(audio_chunk, ..., word_timestamps=False) -> TranscriptionResult`
    - `transcribe_file(audio_path, chunking_result=None, **opts) -> BatchTranscriptionResult`
    - `get_transcriber(**kwargs) -> WhisperTranscriber`
  - `enhanced_transcribe_with_analysis(audio_path, chunking_result, bucket_seconds=4.0, gap_tolerance=0.25, gap_threshold=1.5, enable_overlap_detection=True, **kwargs) -> Dict[str, Any]`

## Configuration
- Driven by `config/default.yaml` and `config/production.yaml`
- Processing: speed, chunking, silence detection
- Transcription: model, device, compute_type, language

## Usage Examples
- CLI transcribe invokes file processor → chunker → transcriber
- Enhanced path triggers 4s window analysis after transcription

## Implementation Details
- Overlap-aware merging of chunk segments
- Device/compute auto-routing via `ResourceDetector`
- Optional word timestamps for analysis

## Testing
- Core tests recommended: chunk boundaries, merging, confidence calc

## Troubleshooting
- If ffmpeg not found, install and add to PATH (Windows)
- If faster-whisper/torch missing, install CPU-only first for quick tests




<!-- AGENTS_analytics.md -->

# Analytics Module - Agent Documentation

## Module Overview
- Timing analysis (4-second windows), cadence stats, uncertainty detection, speaker diarization

## API Reference
- `src/analytics/timing_analyzer.py`
  - `TimingAnalyzer.analyze_timing(transcription_result, speaker_timeline=None) -> (buckets, cadence)`
- `src/post/segmenter.py` / `src/post/cadence.py` / `src/post/assembler.py`
  - Bucketing, gap stats, records assembly
- `src/analytics/uncertainty_detector.py`
  - `UncertaintyDetector.analyze_uncertainty(transcription_result, audio_path=None) -> UncertaintyAnalysis`
- `src/analytics/speaker_analyzer.py`
  - `SpeakerAnalyzer.perform_diarization(audio_path) -> DiarizationResult`

## Configuration
- `config/default.yaml` → `analytics` section: enable flags, thresholds, timing settings

## Usage Examples
- CLI enhanced analysis: `--enhanced-analysis` to produce enhanced outputs
- CLI `analyze quality` and `analyze speakers` commands

## Implementation Details
- Population variance (ddof=0) for gap analysis
- Fallbacks when pyannote is unavailable (Windows/dev env)

## Testing
- Unit tests for gap stats, classification, record validation

## Troubleshooting
- Ensure word timestamps are enabled for timing analysis
- pyannote may require HF token on non-Windows platforms




<!-- AGENTS_utils.md -->

# Utils Module - Agent Documentation

## Module Overview
- Configuration, logging, environment loading, encoding helpers

## API Reference
- `src/utils/config.py`
  - `load_config(name="default", **overrides) -> TalkGPTConfig`
  - `get_config() -> TalkGPTConfig`
  - `ConfigManager.save_config(config, filename)`
- `src/utils/logger.py`
  - `TalkGPTLogger` (Rich console, per-file logs, rotating files)
  - `get_logger(name)`, `get_file_logger(filename)`, `setup_logging(config)`
- `src/utils/env_loader.py`
  - `.ensure_environment_loaded()` sets OpenMP/encoding vars and .env

## Configuration
- YAML files in `config/`; env overrides via `TALKGPT_*`

## Usage Examples
- CLI and scripts call `load_config("default")` and `setup_logging()` before pipeline

## Implementation Details
- Rich logging for console and files; JSON format optional
- Global logger instance for consistent handlers

## Testing
- Validate `save_config`, env overrides, log setup without duplicate handlers

## Troubleshooting
- On Windows terminals, ensure UTF-8 output; use `utils.encoding` where needed




<!-- AGENTS_cli.md -->

# CLI Module - Agent Documentation

## Module Overview
- Entry point and commands for transcription, batch, analyze, config, status, benchmark, doctor

## Commands
- `transcribe <input_path>`: single-file transcription with options
- `batch <input_dir>`: multi-file processing or enqueue to workers (future)
- `analyze speakers|quality`: run advanced analyses
- `config show|set|validate`: manage config
- `status system|jobs`: hardware and queue status
- `benchmark`: quick performance measurement
- `doctor`: preflight checks

## Configuration
- `config/cli.yaml` overrides; CLI flags take highest precedence

## Notes
- On Windows terminals, UTF-8 may require fallback; `utils.encoding.force_utf8_stdio` is used




<!-- AGENTS_mcp.md -->

# MCP Module - Agent Documentation

## Module Overview
- Minimal HTTP-based MCP-like server exposing a `transcribe_audio` tool for agents.

## API Reference
- `POST /tools/transcribe_audio`
  - Request: `{ input_path, output_dir?, formats?, enhanced_analysis?, language? }`
  - Response: `{ input_file, output_directory, output_files, processing_time, processing_speed }`

## Configuration
- `config/mcp.yaml` (server host/port, logging level, tool toggles)

## Usage
- Local: `uvicorn src.mcp.server:app --host 0.0.0.0 --port 8000`
- Script: `python scripts/start_mcp_server.py`

## Notes
- Intended to evolve to JSON-RPC/WebSockets; current MVP uses HTTP JSON




<!-- AGENTS_workers.md -->

# Workers Module - Agent Documentation

## Module Overview
- Celery worker integration for queued transcription jobs backed by Redis.

## API Reference
- `src/workers/celery_app.py`: Celery app (broker from `REDIS_URL`)
- `src/workers/task_manager.py`: tasks
  - `transcribe_file_task(input_path, output_dir?, enhanced_analysis?, formats?, language?) -> dict`

## CLI Integration
- `status jobs` queries worker state via Celery inspect
- Future: `batch --queue` to enqueue jobs instead of inline processing

## Configuration
- Broker: `REDIS_URL` env, default `redis://localhost:6379/0`

## Notes
- Ensure ffmpeg is available in the worker image/environment

<!-- END:GENERATED -->