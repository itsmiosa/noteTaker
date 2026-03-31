#!/usr/bin/env python3
"""
lecture_notes.py — Transcribe a class recording and generate structured notes.

Requirements:
    pip install openai-whisper google-genai torch-directml

Usage:
    python lecture_notes.py recording.mp3
    python lecture_notes.py recording.mp3 --model medium   # better accuracy (slower)
    python lecture_notes.py recording.mp3 --output notes.md

API key:
    export GEMINI_API_KEY="your-key-here"
    Get a free key at: https://aistudio.google.com
"""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def transcribe(audio_path: str, model_size: str) -> str:
    """Transcribe audio using local OpenAI Whisper."""
    try:
        import whisper
        import torch
    except ImportError:
        print("ERROR: whisper or torch not installed.")
        sys.exit(1)

    # Automatically determine the best hardware
    device_name = "CPU"
    device_target = "cpu"
    use_fp16 = True

    if torch.cuda.is_available():
        device_name = "NVIDIA GPU"
        device_target = "cuda"
    else:
        try:
            import torch_directml
            device_name = "AMD/DirectML"
            device_target = torch_directml.device()
            use_fp16 = False # Prevent AMD crashes
        except ImportError:
            pass # Default to CPU

    print(f"[1/3] Loading Whisper model '{model_size}' to {device_name} …")
    
    # Always load to CPU first to prevent deserialization crashes
    model = whisper.load_model(model_size, device="cpu")

    # Apply the sparse tensor fix only if using DirectML
    if "dml" in str(device_target).lower():
        model.alignment_heads = model.alignment_heads.to_dense()

    # Move model to the final detected hardware
    model = model.to(device_target)

    print(f"[2/3] Transcribing '{audio_path}' …  (this may take a minute)")
    result = model.transcribe(audio_path, verbose=False, fp16=use_fp16)
    transcript = result["text"].strip()

    print(f"      Done — {len(transcript.split()):,} words transcribed.")
    return transcript


def generate_notes(transcript: str, api_key: str | None) -> str:
    """Send transcript to Gemini and get back structured notes."""
    try:
        from google import genai
    except ImportError:
        print("ERROR: google-genai not installed. Run:  pip install google-genai")
        sys.exit(1)

    import os
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("ERROR: No Gemini API key found. Set GEMINI_API_KEY or pass --api-key.")
        print("       Get a free key at: https://aistudio.google.com")
        sys.exit(1)

    client = genai.Client(api_key=key)

    print("[3/3] Generating notes with Gemini …")

    prompt = f"""You are an expert note-taker. Below is a transcript of a class lecture.
Produce comprehensive, well-structured notes in Markdown. Include exactly these four sections:

1. **Summary** — 3–5 sentence overview of the entire lecture.
2. **Key Points** — Bullet list of the most important concepts, facts, and arguments.
3. **Headings & Sections** — Re-organise the lecture content into clearly labelled sections with sub-bullets. Use ## for main headings and ### for sub-headings.
4. **Review Questions** — 5–8 questions a student could use to test their understanding.

Keep the notes factual and grounded in the transcript. Do not invent content.

---
TRANSCRIPT:
{transcript}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


def save_transcript(transcript: str, transcript_path: str) -> None:
    Path(transcript_path).write_text(transcript, encoding="utf-8")
    print(f"✓ Transcript saved to '{transcript_path}'")


def save_notes(notes: str, output_path: str) -> None:
    Path(output_path).write_text(notes, encoding="utf-8")
    print(f"✓ Notes saved to '{output_path}'")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Transcribe a lecture recording and generate structured notes."
    )
    parser.add_argument("audio", help="Path to audio file (.mp3, .wav, .m4a, .ogg, …)")
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). Larger = slower but more accurate.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown file (default: <audio_name>_notes.md)",
    )
    parser.add_argument(
        "--output-dir",
        default="./summarized_text",
        help="Output directory for transcript and notes (default: ./summarized_text)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gemini API key (default: reads GEMINI_API_KEY env var)",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"ERROR: File not found: {audio_path}")
        sys.exit(1)

    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = audio_path.stem
    transcript_path = output_dir / (stem + "_transcript.txt")
    output_path = args.output or output_dir / (stem + "_notes.md")

    transcript = transcribe(str(audio_path), args.model)
    save_transcript(transcript, str(transcript_path))
    notes = generate_notes(transcript, args.api_key)
    save_notes(notes, str(output_path))

    print("\n── Preview (first 600 chars) ──────────────────────────────────")
    print(notes[:600])
    print("…")


if __name__ == "__main__":
    main()