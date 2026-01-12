# VibeVoice API Implementation Guide

## Overview

This document outlines the API contract that the OSINT Manager application expects from the VibeVoice FastAPI service for voice training/upload functionality. This guide ensures compatibility between the OSINT Manager backend and the VibeVoice-API service.

## Changes Summary

The OSINT Manager has been updated to:
- **Remove fine-tuning mode** - Only simple voice upload is supported
- **Use new endpoint**: `/voices/upload` instead of `/train`
- **Simplified parameters**: Only `voice_file` and `voice_name` are sent
- **Immediate response**: No async job polling for voice uploads

## Required Endpoint

### POST `/voices/upload`

Upload and process a custom voice file for use in TTS generation.

**Endpoint**: `POST {baseUrl}/voices/upload`

**Content-Type**: `multipart/form-data`

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `voice_file` | File | Yes | Audio file(s) (MP3 or WAV format). Multiple files can be sent by appending multiple files with the same field name. |
| `voice_name` | String | Yes | Name for the voice (e.g., "en-John_man", "my_custom_voice") |

#### Request Format

The OSINT Manager sends requests in the following format:

```python
formData = FormData()
formData.append('voice_name', 'en-John_man')
formData.append('voice_file', fileStream1, 'audio1.wav')
formData.append('voice_file', fileStream2, 'audio2.wav')  # Multiple files supported
```

#### cURL Example

```bash
curl -X POST "http://server-ai.mrhelpmann.com:8008/voices/upload" \
     -F "voice_file=@my_voice.mp3" \
     -F "voice_name=my_custom_voice"
```

For multiple files (if supported):

```bash
curl -X POST "http://server-ai.mrhelpmann.com:8008/voices/upload" \
     -F "voice_file=@audio1.wav" \
     -F "voice_file=@audio2.wav" \
     -F "voice_name=my_custom_voice"
```

#### Success Response (200 OK)

```json
{
  "voice_name": "my_custom_voice",
  "message": "Voice uploaded successfully",
  "file_path": "voices/my_custom_voice.wav"
}
```

**Alternative acceptable response formats:**

The OSINT Manager backend can handle these response formats:

1. **Direct response**:
```json
{
  "voice_name": "my_custom_voice"
}
```

2. **Wrapped in data field**:
```json
{
  "data": {
    "voice_name": "my_custom_voice"
  }
}
```

3. **Success status**:
```json
{
  "status": "success",
  "voice_name": "my_custom_voice",
  "message": "Voice uploaded successfully"
}
```

#### Error Responses

**400 Bad Request** - Invalid request:
```json
{
  "error": "Invalid file format",
  "message": "Only MP3 and WAV files are supported"
}
```

**409 Conflict** - Voice name already exists:
```json
{
  "error": "Voice name already exists",
  "message": "A voice with this name already exists"
}
```

**429 Too Many Requests** - Rate limit exceeded:
```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later."
}
```

**500 Internal Server Error**:
```json
{
  "error": "Internal server error",
  "message": "An error occurred while processing the voice file"
}
```

## Implementation Checklist

Verify your VibeVoice-API implementation includes:

- [ ] Endpoint `/voices/upload` accepts POST requests
- [ ] Accepts `multipart/form-data` content type
- [ ] Handles `voice_file` file parameter (supports multiple files)
- [ ] Handles `voice_name` string parameter
- [ ] Returns `voice_name` in response (required for OSINT Manager)
- [ ] Returns appropriate error codes (400, 409, 429, 500)
- [ ] Processes audio files (format conversion, normalization if needed)
- [ ] Stores voice files in accessible location
- [ ] Validates file format (MP3, WAV)
- [ ] Validates file duration (if applicable)

## File Requirements

Based on the VibeVoice-FastAPI documentation, voice files should be:

- **Format**: MP3 or WAV (WAV recommended)
- **Duration**: 1-30 seconds
- **Content**: Clean speech sample (single speaker, minimal background noise)
- **Processing**: The API should convert to:
  - WAV format
  - 24,000 Hz sampling rate
  - Mono channel
  - Normalized to -25 dB FS

## Testing the Implementation

### Test 1: Basic Upload

```bash
curl -X POST "http://your-server:8008/voices/upload" \
     -F "voice_file=@test_voice.wav" \
     -F "voice_name=test_voice"
```

**Expected**: 200 OK with `voice_name` in response

### Test 2: Invalid Format

```bash
curl -X POST "http://your-server:8008/voices/upload" \
     -F "voice_file=@invalid.txt" \
     -F "voice_name=test_voice"
```

**Expected**: 400 Bad Request with error message

### Test 3: Missing Parameters

```bash
curl -X POST "http://your-server:8008/voices/upload" \
     -F "voice_file=@test_voice.wav"
```

**Expected**: 400 Bad Request (missing `voice_name`)

### Test 4: Duplicate Voice Name

```bash
# First upload
curl -X POST "http://your-server:8008/voices/upload" \
     -F "voice_file=@test_voice.wav" \
     -F "voice_name=test_voice"

# Second upload with same name
curl -X POST "http://your-server:8008/voices/upload" \
     -F "voice_file=@test_voice2.wav" \
     -F "voice_name=test_voice"
```

**Expected**: First request succeeds, second returns 409 Conflict

## OSINT Manager Integration Details

### Request Flow

1. User uploads voice files in OSINT Manager UI
2. OSINT Manager backend receives files and stores temporarily
3. Backend sends POST request to VibeVoice-API `/voices/upload` endpoint
4. Backend expects immediate response with `voice_name`
5. Backend assigns voice to puppet and returns success to frontend

### Response Handling

The OSINT Manager backend (`VibeVoiceService.trainVoice`) handles responses in this order:

1. Checks for error fields: `response.error`, `response.status === 'error'`
2. Extracts `voice_name` from:
   - `response.data.voice_name` (if wrapped in data field)
   - `response.voice_name` (if direct)
3. Falls back to requested `voice_name` if API doesn't return one
4. Throws error if no `voice_name` is available

### Error Handling

The OSINT Manager backend will:
- Log errors with full response details
- Throw errors that bubble up to the API controller
- Return appropriate HTTP status codes to the frontend
- Display user-friendly error messages

## Migration Notes

If migrating from the old `/train` endpoint:

### Old Implementation (Deprecated)

```
POST /train
- training_mode: 'simple_upload' | 'fine_tuning'
- voice_name: string
- files: File[] (parameter name: 'files')
- transcriptions?: string[]
- transcription_backend?: string
- epochs?: number
- learning_rate?: number
- base_model?: string
```

### New Implementation (Current)

```
POST /voices/upload
- voice_name: string
- voice_file: File[] (parameter name: 'voice_file', supports multiple files)
```

**Key Differences:**
1. Endpoint changed from `/train` to `/voices/upload`
2. Parameter name changed from `files` to `voice_file`
3. Removed all fine-tuning parameters
4. Removed `training_mode` parameter
5. Immediate response expected (no async job/task_id)

## Compatibility Notes

- The OSINT Manager currently sends multiple files by appending multiple files with the same `voice_file` field name
- If your API only accepts a single file, you may need to:
  - Accept only the first file, OR
  - Process multiple files and combine them, OR
  - Update OSINT Manager to send only one file
- The OSINT Manager expects the `voice_name` in the response to match the uploaded voice
- Voice names are used as identifiers in the OSINT Manager database

## Additional Resources

- [VibeVoice-FastAPI Documentation](https://github.com/VultureZZ/VibeVoice-FastAPI)
- OSINT Manager VibeVoice Service: `api/src/services/VibeVoiceService.ts`
- OSINT Manager Voice Controller: `api/src/controllers/VoiceController.ts`

## Questions or Issues

If you encounter compatibility issues:

1. Check that the endpoint path matches exactly: `/voices/upload`
2. Verify parameter names: `voice_file` and `voice_name`
3. Ensure response includes `voice_name` field
4. Check error response format matches expected structure
5. Verify file upload handling supports multipart/form-data
