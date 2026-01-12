# 🎙️ VibeVoice FastAPI - Multi-Speaker TTS API

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Original Project](https://img.shields.io/badge/Original-VibeVoice-orange)](https://github.com/microsoft/VibeVoice)

A production-ready FastAPI wrapper for Microsoft's VibeVoice model, enabling high-quality multi-speaker text-to-speech generation through a REST API with status tracking and queue management.

## ✨ Features

- 🎯 **Multi-Speaker TTS**: Generate conversations with up to 4 distinct speakers
- ⚡ **Asynchronous Processing**: Queue-based system handles multiple requests efficiently
- 📊 **Status Tracking**: Real-time job status and queue position monitoring
- 🔄 **Rate Limiting**: Built-in protection against API abuse (10 requests/minute)
- 🎵 **Voice Presets**: Pre-configured voice samples for immediate use
- 📁 **File Management**: Automatic output file handling and cleanup
- 🐳 **Docker Ready**: Easy deployment with containerization support

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- NVIDIA GPU with CUDA support (recommended)
- At least 8GB GPU memory for optimal performance

### Installation

#### Option 1: Standard Installation with uv (Recommended)
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone this repository
git clone https://github.com/dontriskit/VibeVoice-FastAPI
cd VibeVoice-FastAPI

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -e .
```

#### Option 2: Traditional pip Installation
```bash
# Clone this repository
git clone https://github.com/dontriskit/VibeVoice-FastAPI
cd VibeVoice-FastAPI

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

#### Option 3: Docker Installation
```bash
# Using NVIDIA PyTorch Container
sudo docker run --privileged --net=host --ipc=host \
  --ulimit memlock=-1:-1 --ulimit stack=-1:-1 --gpus all \
  --rm -it nvcr.io/nvidia/pytorch:24.07-py3

# Inside container
git clone <your-repo-url>
cd VibeVoice-FastAPI
pip install -r requirements.txt
pip install -e .
```

### Starting the API Server

```bash
# Basic usage (defaults to 1.5B model, port 8000)
python main.py

# Use the Realtime model (streaming, single speaker only)
python main.py --model realtime

# Custom host and port
python main.py --host 0.0.0.0 --port 8008

# Custom auto-unload timeout (in seconds, default: 10)
python main.py --unload-timeout 30

# Disable auto-unload (keep model loaded permanently)
python main.py --unload-timeout 0

# All options combined
python main.py --model 1.5b --host 0.0.0.0 --port 8008 --unload-timeout 30

# Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000` with interactive documentation at `http://localhost:8000/docs`.

**Note:** The model uses lazy loading - it will be loaded automatically on the first generation request. If no requests are made for the specified timeout period (default: 10 seconds), the model will be automatically unloaded to free GPU memory.

## 📚 API Documentation

### Available Models

| Model | Context Length | Generation Length | Multi-Speaker | GPU Memory | Hugging Face |
|-------|----------------|-------------------|--------------|-----------|--------------|
| VibeVoice-1.5B | 64K tokens | ~90 minutes | ✅ Yes (up to 4) | ~8GB | [microsoft/VibeVoice-1.5B](https://huggingface.co/microsoft/VibeVoice-1.5B) |
| VibeVoice-Realtime-0.5B | Streaming | Real-time (~300ms latency) | ❌ No (single speaker) | ~4GB | [microsoft/VibeVoice-Realtime-0.5B](https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B) |

**Model Selection:**
- **1.5B Model (Default)**: Best for multi-speaker conversations, podcasts, and long-form content. Supports up to 4 distinct speakers in a single generation.
- **Realtime Model**: Optimized for streaming input and low-latency generation. Single speaker only, ideal for real-time applications.

### API Endpoints

#### 1. Generate Audio
**POST** `/generate`

Submit a text-to-speech generation request. Supports multi-speaker conversations (1.5B model) or single speaker (realtime model).

**Request Body:**
```json
{
  "script": "Speaker 1: Hello, how are you today?\nSpeaker 2: I'm doing great, thanks for asking!",
  "speaker_names": ["en-Alice_woman", "en-Carter_man"],
  "cfg_scale": 1.3
}
```

**Parameters:**
- `script` (string, required): The dialogue script. Format: `"Speaker N: dialogue text"`
- `speaker_names` (array, required): List of voice names matching speaker order. Must match number of unique speakers in script.
- `cfg_scale` (float, optional): Classifier-free guidance scale. Range: 1.0-2.0. Default: 1.3. Higher values = more adherence to voice characteristics.

**Response (202 Accepted):**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "message": "Job accepted and placed in queue.",
  "queue_position": 1
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request format or parameters
- `429 Too Many Requests`: Rate limit exceeded (10 requests/minute)
- `503 Service Unavailable`: Model not loaded or service unavailable

#### 2. Check Task Status
**GET** `/status/{task_id}`

Monitor the progress of your generation job. Returns real-time status and queue position.

**Path Parameters:**
- `task_id` (string, required): The task ID returned from `/generate`

**Response (200 OK):**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "running",
  "queue_position": 0,
  "generation_time": null,
  "error": null,
  "result_path": null
}
```

**Status Values:**
- `queued`: Job is waiting in queue
- `loading_model`: Model is being loaded (first request)
- `running`: Job is currently being processed
- `completed`: Job finished successfully (check `result_path` for file location)
- `failed`: Job encountered an error (check `error` field for details)

**Error Responses:**
- `404 Not Found`: Task ID not found

#### 3. Download Result
**GET** `/result/{task_id}`

Download the generated audio file in WAV format.

**Path Parameters:**
- `task_id` (string, required): The task ID from a completed generation

**Response:**
- `200 OK`: Audio file (WAV format, 24kHz, mono)
- `400 Bad Request`: Task not completed yet
- `404 Not Found`: Task ID not found or result file missing

**Example:**
```bash
curl -o output.wav "http://localhost:8000/result/123e4567-e89b-12d3-a456-426614174000"
```

#### 4. List Available Voices
**GET** `/voices`

Get all available voice presets (both built-in and user-uploaded).

**Response (200 OK):**
```json
[
  "en-Alice_woman",
  "en-Carter_man",
  "en-Frank_man",
  "en-Mary_woman_bgm",
  "zh-Bowen_man",
  "zh-Xinran_woman",
  "my_custom_voice"
]
```

**Note:** Voice names are automatically discovered from:
- Built-in voices: `demo/voices/` directory
- User-uploaded voices: `voices/` directory

#### 5. Upload Custom Voice
**POST** `/voices/upload`

Upload and process a custom voice file for use in TTS generation.

**Request (multipart/form-data):**
- `voice_file` (file, required): Audio file (MP3 or WAV format)
- `voice_name` (string, optional): Custom name for the voice. If not provided, filename (sanitized) will be used.

**Voice File Requirements:**
- **Format**: MP3 or WAV
- **Duration**: 1-30 seconds
- **Content**: Clean speech sample (single speaker, minimal background noise)

**Processing:**
The uploaded file will be automatically converted to:
- WAV format
- 24,000 Hz sampling rate
- Mono channel
- Normalized to -25 dB FS

**Response (201 Created):**
```json
{
  "message": "Voice uploaded successfully",
  "voice_name": "my_custom_voice",
  "file_path": "voices/my_custom_voice.wav"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid file format, duration out of range, or processing error
- `409 Conflict`: Voice name already exists
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error during processing

**Example (cURL):**
```bash
curl -X POST "http://localhost:8000/voices/upload" \
     -F "voice_file=@my_voice.mp3" \
     -F "voice_name=my_custom_voice"
```

**Example (Python):**
```python
import requests

with open("my_voice.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:8000/voices/upload",
        files={"voice_file": f},
        data={"voice_name": "my_custom_voice"}
    )
print(response.json())
```

#### 6. Delete Custom Voice
**DELETE** `/voices/{voice_name}`

Delete a user-uploaded voice from the system. Built-in voices cannot be deleted.

**Path Parameters:**
- `voice_name` (string, required): Name of the voice to delete

**Response (200 OK):**
```json
{
  "message": "Voice deleted successfully",
  "voice_name": "my_custom_voice"
}
```

**Error Responses:**
- `400 Bad Request`: Attempting to delete a built-in voice
- `404 Not Found`: Voice not found
- `500 Internal Server Error`: Failed to delete voice file

**Example:**
```bash
curl -X DELETE "http://localhost:8000/voices/my_custom_voice"
```

### Script Format

Your script should follow this format:
```
Speaker 1: First person's dialogue here.
Speaker 2: Second person's response.
Speaker 1: More dialogue from first person.
```

**Important Notes:**
- Each speaker line must start with "Speaker" followed by a number (1, 2, 3, or 4)
- Speaker numbers should be consistent throughout the script
- Provide voice names in `speaker_names` array matching the speaker order
- The number of unique speakers must match the length of `speaker_names` array
- Maximum 4 speakers supported (1.5B model only; realtime model supports 1 speaker)

**Example Script:**
```
Speaker 1: Welcome to our podcast today!
Speaker 2: Thanks for having me.
Speaker 1: Let's start with your background.
Speaker 2: I've been working in AI for ten years.
Speaker 3: That's fascinating! Can you tell us more?
```

With corresponding `speaker_names`: `["en-Alice_woman", "en-Carter_man", "en-Frank_man"]`

## 💡 Usage Examples

### Python Client Example
```python
import requests
import time

# Submit generation request
response = requests.post("http://localhost:8000/generate", json={
    "script": "Speaker 1: Welcome to our podcast!\nSpeaker 2: Thanks for having me!",
    "speaker_names": ["en-Alice_woman", "en-Carter_man"],
    "cfg_scale": 1.3
})

task_id = response.json()["task_id"]
print(f"Task submitted: {task_id}")

# Poll for completion
while True:
    status_response = requests.get(f"http://localhost:8000/status/{task_id}")
    status = status_response.json()["status"]

    if status == "completed":
        # Download the result
        audio_response = requests.get(f"http://localhost:8000/result/{task_id}")
        with open("output.wav", "wb") as f:
            f.write(audio_response.content)
        print("Audio saved as output.wav")
        break
    elif status == "failed":
        print("Generation failed")
        break
    else:
        print(f"Status: {status}")
        time.sleep(5)
```

### cURL Examples
```bash
# Submit generation request
curl -X POST "http://localhost:8000/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "script": "Speaker 1: Hello world!\nSpeaker 2: How are you?",
       "speaker_names": ["en-Alice_woman", "en-Carter_man"],
       "cfg_scale": 1.3
     }'

# Check status
curl "http://localhost:8000/status/YOUR_TASK_ID"

# Download result
curl -o output.wav "http://localhost:8000/result/YOUR_TASK_ID"

# List voices
curl "http://localhost:8000/voices"

# Upload custom voice
curl -X POST "http://localhost:8000/voices/upload" \
     -F "voice_file=@my_voice.mp3" \
     -F "voice_name=my_custom_voice"

# Delete custom voice
curl -X DELETE "http://localhost:8000/voices/my_custom_voice"
```

## ⚙️ Configuration

### Model Selection

You can switch between models using command-line arguments - **no code changes required**:

```bash
# Use the 1.5B model (default, faster, less memory)
python main.py --model 1.5b

# Use the Realtime model (streaming, single speaker, low latency)
python main.py --model realtime
```

**Available Models:**
- `1.5b` - Microsoft VibeVoice-1.5B (default)
  - **Context**: 64K tokens
  - **Generation Length**: ~90 minutes
  - **Multi-Speaker**: Yes (up to 4 speakers)
  - **GPU Memory**: ~8GB
  - **Use Cases**: Multi-speaker conversations, podcasts, long-form content
  - **Hugging Face**: [microsoft/VibeVoice-1.5B](https://huggingface.co/microsoft/VibeVoice-1.5B)

- `realtime` - VibeVoice-Realtime-0.5B
  - **Context**: Streaming input
  - **Latency**: ~300ms (real-time)
  - **Multi-Speaker**: No (single speaker only)
  - **GPU Memory**: ~4GB
  - **Use Cases**: Real-time applications, streaming TTS, single-speaker generation
  - **Hugging Face**: [microsoft/VibeVoice-Realtime-0.5B](https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B)

**Note:** The 7B model (WestZhang/VibeVoice-Large-pt) is no longer available on Hugging Face.

### Auto-Unload Feature

The API includes an automatic model unloading feature to free GPU memory when the model is not in use:

- **Default timeout**: 10 seconds of inactivity
- **Customizable**: Use `--unload-timeout` to set your preferred timeout
- **Disable**: Set `--unload-timeout 0` to keep the model loaded permanently
- **Automatic reload**: Model will be automatically reloaded on the next request

**Examples:**
```bash
# 30 second timeout
python main.py --unload-timeout 30

# Disable auto-unload (keep model in memory)
python main.py --unload-timeout 0

# 5 second timeout for quick memory release
python main.py --unload-timeout 5
```

**How it works:**
1. Model loads automatically on first generation request (lazy loading)
2. After each use, a timer tracks inactivity
3. If no requests are made within the timeout period, the model is fully unloaded
4. GPU memory is completely released (same as restarting the application)
5. Next request will automatically reload the model

### Voice Management

#### Adding Custom Voices

You can add custom voices in two ways:

**Method 1: Using the API (Recommended)**
```bash
curl -X POST "http://localhost:8000/voices/upload" \
     -F "voice_file=@my_voice.mp3" \
     -F "voice_name=my_custom_voice"
```

**Method 2: Manual Upload**
1. Place your voice file in the `voices/` directory
2. File must be WAV format, 24kHz, mono
3. Duration: 1-30 seconds
4. Normalized to -25 dB FS
5. The API will automatically discover it on next request

**Voice File Requirements:**
- **Format**: WAV (recommended) or MP3
- **Duration**: 1-30 seconds
- **Quality**: Clean speech, minimal background noise
- **Content**: Single speaker, clear pronunciation
- **Sampling Rate**: Will be converted to 24,000 Hz automatically
- **Channels**: Will be converted to mono automatically

**Best Practices:**
- Use high-quality recordings (studio quality preferred)
- Record in a quiet environment
- Use consistent speaking style throughout the sample
- Include natural pauses and intonation
- Avoid background music or noise
- 5-15 seconds is optimal duration

**Voice Naming:**
- Voice names are derived from filenames (without extension)
- Special characters are automatically sanitized
- Use descriptive names: `john_american_male`, `sarah_british_female`
- Built-in voices use format: `{lang}-{name}_{gender}` (e.g., `en-Alice_woman`)

**Voice Directories:**
- **Built-in voices**: `demo/voices/` - Pre-installed voices (read-only)
- **User voices**: `voices/` - Your custom voices (can be uploaded/deleted via API)

### Rate Limiting
Current limit: 10 requests per minute per IP. Modify in `main.py`:
```python
@limiter.limit("10/minute")  # Change this value
```

## 🚨 Important Notes

### Chinese Speech Stability
For optimal Chinese speech generation:
- Use English punctuation (commas and periods only)
- The 1.5B model provides good stability for both English and Chinese
- Avoid special Chinese quotation marks

### Background Music
The model may spontaneously generate background music:
- Voice samples with BGM increase the likelihood
- Introductory phrases ("Welcome to", "Hello") may trigger BGM
- Using "Alice" voice preset has higher BGM probability
- This is an intentional feature, not a bug

### Memory Requirements
- **1.5B model**: ~8GB GPU memory
- **Realtime model**: ~4GB GPU memory
- CPU inference is supported but significantly slower (not recommended for production)

## 📋 System Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   FastAPI       │───▶│  Task Queue  │───▶│ Worker Thread   │
│   Web Server    │    │ (in-memory)  │    │ (GPU Inference) │
└─────────────────┘    └──────────────┘    └─────────────────┘
        │                       │                     │
        ▼                       ▼                     ▼
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Rate Limiter  │    │ Job Tracking │    │ Audio Output    │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

**Key Features:**
- Single-process architecture for simplicity
- In-memory queue ensures FIFO processing
- Background worker prevents blocking the web server
- Status tracking provides real-time updates

## 📄 License & Attribution

This project is a FastAPI wrapper around Microsoft's VibeVoice model. Please refer to the [original VibeVoice repository](https://github.com/microsoft/VibeVoice) for licensing terms and model details.

## ⚠️ Ethical Use & Limitations

**Responsible AI Usage:**
- Disclose AI-generated content when sharing
- Ensure compliance with local laws and regulations
- Verify content accuracy and avoid misleading applications
- Do not use for deepfakes or disinformation

**Technical Limitations:**
- English and Chinese only
- No overlapping speech generation
- Speech synthesis only (no background noise/music control)
- Not recommended for commercial use without additional testing

**Model is intended for research and development purposes. Use responsibly.**
