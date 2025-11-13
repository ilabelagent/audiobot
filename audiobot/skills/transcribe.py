
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from google.cloud import speech
from google.oauth2 import service_account

def transcribe_audio(file_path: Path) -> Dict[str, Any]:
    """Transcribes the given audio file using Google Cloud Speech-to-Text."""
    try:
        # Path to your service account key file
        key_path = Path("peaceful-access-473817-v1-b6c23a77fab4.json")

        # Create credentials from the service account key file
        credentials = service_account.Credentials.from_service_account_file(key_path)

        # Instantiates a client
        client = speech.SpeechClient(credentials=credentials)

        # Reads the audio file into memory
        with open(file_path, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
        )

        # Detects speech in the audio file
        response = client.recognize(config=config, audio=audio)

        transcripts = [result.alternatives[0].transcript for result in response.results]
        return {"ok": True, "transcript": " ".join(transcripts)}

    except Exception as e:
        return {"ok": False, "log": str(e)}
