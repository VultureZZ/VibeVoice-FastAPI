import os
import re
import time
import uuid
import queue
import threading
import argparse
import gc
from typing import List, Tuple, Dict, Any, Optional

import torch
import uvicorn
import numpy as np
import librosa
import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# VibeVoice imports
from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor
from transformers.utils import logging

# --- Setup & Configuration ---

logging.set_verbosity_info()
logger = logging.get_logger(__name__)

# --- Rate Limiting & Task Queue ---

limiter = Limiter(key_func=get_remote_address)
# An in-memory queue to hold incoming generation requests.
task_queue = queue.Queue()

# --- Global Variables & Model Loading ---

model: Optional[VibeVoiceForConditionalGenerationInference] = None
processor: Optional[VibeVoiceProcessor] = None
voice_mapper: Optional[Any] = None
tasks: Dict[str, Dict[str, Any]] = {}
selected_model: str = "1.5b"  # Default model
model_lock = threading.Lock()  # Lock for thread-safe model operations
last_used: float = 0.0  # Timestamp of last model usage
unload_timeout: float = 10.0  # Seconds of inactivity before auto-unload (default: 10)
unload_monitor_thread: Optional[threading.Thread] = None
monitor_running = False  # Flag to control the monitor thread

# --- Helper Classes ---

class VoiceMapper:
    def __init__(self, builtin_path: str = "demo/voices", user_path: str = "voices"):
        self.builtin_path = builtin_path
        self.user_path = user_path
        self.voice_presets = {}
        self.available_voices = {}
        self.builtin_voices = set()
        self.user_voices = set()
        self.setup_voice_presets()

    def setup_voice_presets(self):
        """Scan both built-in and user voice directories."""
        self.voice_presets = {}
        self.builtin_voices = set()
        self.user_voices = set()

        # Scan built-in voices directory
        if os.path.exists(self.builtin_path):
            wav_files = [f for f in os.listdir(self.builtin_path) if f.lower().endswith('.wav')]
            for wav_file in wav_files:
                name = os.path.splitext(wav_file)[0]
                full_path = os.path.join(self.builtin_path, wav_file)
                if os.path.exists(full_path):
                    self.voice_presets[name] = full_path
                    self.builtin_voices.add(name)
            logger.info(f"Found {len(self.builtin_voices)} built-in voices in {self.builtin_path}")
        else:
            logger.warning(f"Built-in voices directory not found at {self.builtin_path}")

        # Scan user voices directory
        if os.path.exists(self.user_path):
            wav_files = [f for f in os.listdir(self.user_path) if f.lower().endswith('.wav')]
            for wav_file in wav_files:
                name = os.path.splitext(wav_file)[0]
                full_path = os.path.join(self.user_path, wav_file)
                if os.path.exists(full_path):
                    # User voices can override built-in voices with same name
                    if name not in self.builtin_voices:
                        self.voice_presets[name] = full_path
                        self.user_voices.add(name)
                    else:
                        logger.warning(f"User voice '{name}' conflicts with built-in voice, skipping")
            logger.info(f"Found {len(self.user_voices)} user voices in {self.user_path}")
        else:
            logger.info(f"User voices directory not found at {self.user_path}, will be created on first upload")

        self.available_voices = {n: p for n, p in self.voice_presets.items() if os.path.exists(p)}
        logger.info(f"Total {len(self.available_voices)} voices available")

    def reload(self):
        """Reload voice presets from directories."""
        self.setup_voice_presets()

    def is_builtin_voice(self, voice_name: str) -> bool:
        """Check if a voice is a built-in voice."""
        return voice_name in self.builtin_voices

    def get_voice_path(self, speaker_name: str) -> str:
        """Get voice file path for a speaker name."""
        # Exact and partial matching logic
        if speaker_name in self.available_voices:
            return self.available_voices[speaker_name]
        speaker_lower = speaker_name.lower()
        for name, path in self.available_voices.items():
            if name.lower() in speaker_lower or speaker_lower in name.lower():
                return path
        if self.available_voices:
            return list(self.available_voices.values())[0]
        raise ValueError("No voice presets available.")

# --- Audio Processing Utility ---

def process_voice_file(
    input_file: UploadFile,
    output_dir: str = "voices",
    target_sr: int = 24000,
    min_duration: float = 1.0,
    max_duration: float = 30.0,
    target_dB_FS: float = -25
) -> Tuple[str, str]:
    """
    Process uploaded voice file to VibeVoice-compatible format.

    Args:
        input_file: Uploaded file object
        output_dir: Directory to save processed file
        target_sr: Target sampling rate (24000 Hz for VibeVoice)
        min_duration: Minimum audio duration in seconds
        max_duration: Maximum audio duration in seconds
        target_dB_FS: Target dB FS for normalization

    Returns:
        Tuple of (voice_name, output_path)

    Raises:
        HTTPException: If file processing fails or validation fails
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Validate file extension
    file_ext = os.path.splitext(input_file.filename)[1].lower()
    if file_ext not in ['.mp3', '.wav']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Only MP3 and WAV files are supported. Got: {file_ext}"
        )

    # Generate voice name from filename or use provided name
    voice_name = os.path.splitext(input_file.filename)[0]
    # Sanitize voice name (remove special characters, spaces)
    voice_name = re.sub(r'[^a-zA-Z0-9_-]', '_', voice_name)
    if not voice_name:
        voice_name = f"voice_{uuid.uuid4().hex[:8]}"

    # Check if voice name already exists
    output_path = os.path.join(output_dir, f"{voice_name}.wav")
    if os.path.exists(output_path):
        raise HTTPException(
            status_code=409,
            detail=f"Voice name '{voice_name}' already exists. Please choose a different name."
        )

    # Save uploaded file temporarily
    temp_path = os.path.join(output_dir, f"temp_{uuid.uuid4().hex[:8]}{file_ext}")
    try:
        with open(temp_path, "wb") as f:
            content = input_file.file.read()
            f.write(content)

        # Load audio with librosa
        try:
            audio, sr = librosa.load(temp_path, sr=target_sr, mono=True)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load audio file: {str(e)}"
            )

        # Validate duration
        duration = len(audio) / target_sr
        if duration < min_duration:
            raise HTTPException(
                status_code=400,
                detail=f"Audio duration ({duration:.2f}s) is too short. Minimum: {min_duration}s"
            )
        if duration > max_duration:
            raise HTTPException(
                status_code=400,
                detail=f"Audio duration ({duration:.2f}s) is too long. Maximum: {max_duration}s"
            )

        # Normalize audio (target_dB_FS: -25)
        # Calculate RMS and normalize to target dB FS
        rms = np.sqrt(np.mean(audio**2))
        if rms > 1e-6:
            target_linear = 10 ** (target_dB_FS / 20.0)
            audio = audio * (target_linear / rms)

        # Ensure audio is in valid range [-1, 1]
        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val

        # Save as WAV file
        sf.write(output_path, audio, target_sr)

        logger.info(f"Processed voice file: {voice_name} ({duration:.2f}s, {target_sr}Hz, mono)")

        return voice_name, output_path

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing voice file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process voice file: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

def parse_txt_script(txt_content: str) -> Tuple[List[str], List[str]]:
    lines = txt_content.strip().split('\n')
    scripts, speaker_numbers = [], []
    speaker_pattern = r'^Speaker\s+(\d+):\s*(.*)$'
    current_speaker, current_text = None, ""
    for line in lines:
        line = line.strip()
        if not line: continue
        match = re.match(speaker_pattern, line, re.IGNORECASE)
        if match:
            if current_speaker is not None and current_text:
                scripts.append(f"Speaker {current_speaker}: {current_text.strip()}")
                speaker_numbers.append(current_speaker)
            current_speaker, current_text = match.group(1).strip(), match.group(2).strip()
        elif current_text:
            current_text += " " + line
    if current_speaker is not None and current_text:
        scripts.append(f"Speaker {current_speaker}: {current_text.strip()}")
        speaker_numbers.append(current_speaker)
    return scripts, speaker_numbers

# --- Model Management Functions ---

def load_model(model_name: str = None):
    """
    Load the VibeVoice model and processor.

    Args:
        model_name: Model to load ("1.5b" or "7b"). Uses selected_model if None.
    """
    global model, processor, voice_mapper, selected_model, last_used

    with model_lock:
        if model is not None:
            logger.info("Model already loaded, skipping reload.")
            last_used = time.time()
            return

        model_to_load = model_name.lower() if model_name else selected_model.lower()
        logger.info(f"Loading {model_to_load.upper()} model...")

        # Select model path based on model name
        if model_to_load == "7b":
            model_path = "WestZhang/VibeVoice-Large-pt"
        else:
            model_path = "microsoft/VibeVoice-1.5B"

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}, model path: {model_path}")

        # Initialize voice mapper if not already done
        if voice_mapper is None:
            logger.info("Initializing voice mapper...")
            voice_mapper = VoiceMapper(builtin_path="demo/voices", user_path="voices")

        # Load processor and model
        logger.info("Loading processor...")
        processor = VibeVoiceProcessor.from_pretrained(model_path)
        logger.info("Processor loaded. Loading model (this may take several minutes)...")
        
        model = VibeVoiceForConditionalGenerationInference.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
            attn_implementation="sdpa"
        )
        logger.info("Model loaded. Setting to eval mode and configuring inference steps...")
        model.eval()
        model.set_ddpm_inference_steps(num_steps=10)

        last_used = time.time()
        logger.info(f"{model_to_load.upper()} model loaded successfully and ready for inference.")


def unload_model():
    """
    Fully unload the model and processor, clearing GPU memory.
    """
    global model, processor, last_used

    with model_lock:
        if model is None:
            logger.info("Model already unloaded.")
            return

        logger.info("Unloading model and clearing GPU memory...")

        # Move model to CPU and delete
        if hasattr(model, 'cpu'):
            model = model.cpu()

        # Delete model and processor
        del model
        del processor

        # Clear PyTorch cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            # Force garbage collection
            gc.collect()
            torch.cuda.empty_cache()

        model = None
        processor = None
        last_used = 0.0

        logger.info("Model unloaded and GPU memory cleared.")


def ensure_model_loaded():
    """Ensure the model is loaded before use."""
    global model, last_used

    with model_lock:
        if model is None:
            try:
                load_model()
            except Exception as e:
                logger.error(f"Failed to load model: {e}", exc_info=True)
                raise
        else:
            last_used = time.time()


def unload_monitor():
    """
    Background thread that monitors model usage and unloads after timeout.
    """
    global monitor_running, last_used, unload_timeout

    logger.info(f"Model auto-unload monitor started (timeout: {unload_timeout}s)")

    while monitor_running:
        time.sleep(1.0)  # Check every second

        with model_lock:
            if model is not None and last_used > 0:
                time_since_last_use = time.time() - last_used
                if time_since_last_use >= unload_timeout:
                    logger.info(f"Model inactive for {time_since_last_use:.1f}s, auto-unloading...")
                    unload_model()


# --- Background Worker for Inference ---

def generation_worker():
    """
    A dedicated worker thread that continuously processes tasks from the queue.
    """
    logger.info("Generation worker started.")
    while True:
        task_id, script_content, speaker_names, cfg_scale = task_queue.get()
        if task_id is None: # A way to stop the worker thread if needed.
            break

        try:
            logger.info(f"Worker picked up task {task_id}.")
            start_time = time.time()

            # Check if model needs to be loaded and update status
            needs_loading = False
            with model_lock:
                if model is None:
                    needs_loading = True
            
            if needs_loading:
                logger.info(f"Model not loaded, loading now for task {task_id}...")
                tasks[task_id]["status"] = "loading_model"
            
            # Ensure model is loaded before processing (this may take several minutes)
            ensure_model_loaded()
            
            # Update status to running after model is loaded
            if needs_loading:
                logger.info(f"Model loaded successfully, starting generation for task {task_id}...")
                tasks[task_id]["status"] = "running"

            # --- Core Inference Logic ---
            scripts, speaker_numbers = parse_txt_script(script_content)
            if not scripts: raise ValueError("No valid scripts found in the provided text.")

            unique_speakers = sorted(list(set(speaker_numbers)), key=int)
            if len(speaker_names) < len(unique_speakers):
                raise ValueError(f"Script has {len(unique_speakers)} speakers, but only {len(speaker_names)} names were given.")

            name_map = {num: name for num, name in zip(unique_speakers, speaker_names)}
            voice_samples = [voice_mapper.get_voice_path(name_map[num]) for num in unique_speakers]

            inputs = processor(
                text=['\n'.join(scripts)],
                voice_samples=[voice_samples],
                padding=True, return_tensors="pt", return_attention_mask=True
            )

            outputs = model.generate(
                **inputs, max_new_tokens=None, cfg_scale=cfg_scale,
                tokenizer=processor.tokenizer, generation_config={'do_sample': False},
                verbose=False
            )
            # --- End Core Inference Logic ---

            generation_time = time.time() - start_time
            logger.info(f"Task {task_id} finished in {generation_time:.2f}s")

            output_dir = "api_outputs"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{task_id}.wav")
            processor.save_audio(outputs.speech_outputs[0], output_path=output_path)

            tasks[task_id].update({
                "status": "completed",
                "result_path": output_path,
                "generation_time": generation_time
            })

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            if task_id in tasks:
                tasks[task_id].update({"status": "failed", "error": str(e)})
        finally:
            task_queue.task_done()

# --- FastAPI App Definition ---

app = FastAPI(title="VibeVoice API", description="API for long-form multi-speaker TTS")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
async def startup_event():
    global model, processor, voice_mapper, selected_model, unload_monitor_thread, monitor_running

    logger.info(f"Application startup: initializing {selected_model.upper()} model configuration...")

    # Initialize voice mapper (doesn't require model)
    if voice_mapper is None:
        voice_mapper = VoiceMapper(builtin_path="demo/voices", user_path="voices")

    # Model will be loaded on first use (lazy loading)
    # This allows the API to start quickly and load model only when needed

    # Start the background worker thread
    worker_thread = threading.Thread(target=generation_worker, daemon=True)
    worker_thread.start()

    # Start the auto-unload monitor thread
    monitor_running = True
    unload_monitor_thread = threading.Thread(target=unload_monitor, daemon=True)
    unload_monitor_thread.start()

    logger.info(f"Application started. Model will be loaded on first request (auto-unload timeout: {unload_timeout}s).")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    global monitor_running, model

    logger.info("Application shutting down...")

    # Stop the monitor thread
    monitor_running = False

    # Unload model if loaded
    if model is not None:
        unload_model()

    logger.info("Shutdown complete.")

# --- Pydantic Models for API I/O ---

class GenerationRequest(BaseModel):
    script: str = Field(..., description="The full script, e.g., 'Speaker 1: ...\nSpeaker 2: ...'")
    speaker_names: List[str] = Field(..., description="List of voice preset names, e.g., ['en-Alice_woman']")
    cfg_scale: float = Field(1.3, ge=1.0, le=2.0)

class GenerationResponse(BaseModel):
    task_id: str
    status: str
    message: str
    queue_position: int

class TaskStatus(BaseModel):
    task_id: str
    status: str
    queue_position: Optional[int] = None
    error: Optional[str] = None
    result_path: Optional[str] = None
    generation_time: Optional[float] = None

# --- API Endpoints ---

@app.post("/generate", response_model=GenerationResponse, status_code=202)
@limiter.limit("10/minute")
async def generate_audio(request: Request, generation_request: GenerationRequest):
    task_id = str(uuid.uuid4())
    queue_pos = task_queue.qsize() + 1
    tasks[task_id] = {"status": "queued", "queue_position": queue_pos}

    task_queue.put((
        task_id,
        generation_request.script,
        generation_request.speaker_names,
        generation_request.cfg_scale
    ))

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Job accepted and placed in queue.",
        "queue_position": queue_pos
    }

@app.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Dynamically update queue position if still queued
    if task["status"] == "queued":
        try:
            # Find the position in the current queue
            all_queued_tasks = list(task_queue.queue)
            pos = [item[0] for item in all_queued_tasks].index(task_id) + 1
            task["queue_position"] = pos
        except ValueError:
            # Task might have just been picked up, status will update soon
            task["queue_position"] = 0

    return {"task_id": task_id, **task}

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    task = tasks.get(task_id)
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Task not complete. Status: {task['status']}")
    result_path = task.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found.")
    return FileResponse(result_path, media_type="audio/wav", filename=os.path.basename(result_path))

@app.get("/voices", response_model=List[str])
async def list_voices():
    if not voice_mapper: raise HTTPException(status_code=503, detail="VoiceMapper not initialized.")
    return list(voice_mapper.available_voices.keys())

@app.post("/voices/upload")
@limiter.limit("10/minute")
async def upload_voice(
    request: Request,
    voice_file: UploadFile = File(..., description="Voice file (MP3 or WAV)"),
    voice_name: Optional[str] = Form(None, description="Optional custom name for the voice")
):
    """
    Upload and process a voice file for use in TTS generation.

    The file will be converted to:
    - WAV format
    - 24000 Hz sampling rate
    - Mono channel
    - Normalized to -25 dB FS

    Duration must be between 1-30 seconds.
    """
    if not voice_mapper:
        raise HTTPException(status_code=503, detail="VoiceMapper not initialized.")

    try:
        # Process the voice file
        processed_name, output_path = process_voice_file(voice_file)

        # Use custom name if provided
        if voice_name:
            # Sanitize custom name
            voice_name = re.sub(r'[^a-zA-Z0-9_-]', '_', voice_name)
            if voice_name and voice_name != processed_name:
                # Check if new name already exists
                new_output_path = os.path.join("voices", f"{voice_name}.wav")
                if os.path.exists(new_output_path):
                    # Clean up the file we just created
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    raise HTTPException(
                        status_code=409,
                        detail=f"Voice name '{voice_name}' already exists."
                    )
                # Rename the file
                try:
                    os.rename(output_path, new_output_path)
                    processed_name = voice_name
                    output_path = new_output_path
                except OSError as e:
                    # If rename fails, clean up
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to rename voice file: {str(e)}"
                    )

        # Reload voice mapper to include new voice
        voice_mapper.reload()

        return JSONResponse(
            status_code=201,
            content={
                "message": "Voice uploaded successfully",
                "voice_name": processed_name,
                "file_path": output_path
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading voice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload voice: {str(e)}")

@app.delete("/voices/{voice_name}")
async def delete_voice(voice_name: str):
    """
    Delete a user-uploaded voice from the system.

    Built-in voices cannot be deleted.
    """
    if not voice_mapper:
        raise HTTPException(status_code=503, detail="VoiceMapper not initialized.")

    # Check if voice exists
    if voice_name not in voice_mapper.available_voices:
        raise HTTPException(
            status_code=404,
            detail=f"Voice not found: {voice_name}"
        )

    # Check if it's a built-in voice
    if voice_mapper.is_builtin_voice(voice_name):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete built-in voice. Only user-created voices can be deleted."
        )

    # Get the voice file path
    voice_path = voice_mapper.available_voices[voice_name]

    # Verify it's in the user voices directory (not built-in)
    # Normalize paths for comparison
    user_voices_dir = os.path.abspath("voices")
    voice_path_abs = os.path.abspath(voice_path)
    builtin_voices_dir = os.path.abspath("demo/voices")

    if not voice_path_abs.startswith(user_voices_dir) or voice_path_abs.startswith(builtin_voices_dir):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete built-in voice. Only user-created voices can be deleted."
        )

    # Delete the file
    files_deleted = []
    try:
        if os.path.exists(voice_path):
            os.remove(voice_path)
            files_deleted.append(voice_path)
            logger.info(f"Deleted voice: {voice_name} from {voice_path}")
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Voice file not found: {voice_path}"
            )
    except OSError as e:
        logger.error(f"Error deleting voice file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete voice file: {str(e)}"
        )

    # Reload voice mapper to remove deleted voice
    voice_mapper.reload()

    return JSONResponse(
        status_code=200,
        content={
            "message": "Voice deleted successfully",
            "voice_name": voice_name,
            "files_deleted": files_deleted
        }
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VibeVoice FastAPI Server")
    parser.add_argument(
        "--model",
        type=str,
        choices=["1.5b", "7b"],
        default="1.5b",
        help="Model to use: 1.5b (default) or 7b"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--unload-timeout",
        type=float,
        default=10.0,
        help="Seconds of inactivity before auto-unloading model (default: 10.0, set to 0 to disable)"
    )

    args = parser.parse_args()
    selected_model = args.model.lower()
    unload_timeout = args.unload_timeout

    # Ensure voices directory exists
    os.makedirs("voices", exist_ok=True)

    uvicorn.run(app, host=args.host, port=args.port)