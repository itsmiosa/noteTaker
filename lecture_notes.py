#!/usr/bin/env python3
"""
lecture_notes.py — Transcribe a class recording and generate structured notes.

Requirements:
    pip install openai-whisper google-generativeai

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


# ── Helpers ──────────────────────────────────────────────────────────────────

def transcribe(audio_path: str, model_size: str) -> str:
    """Transcribe audio using local OpenAI Whisper."""
    try:
        import whisper
    except ImportError:
        print("ERROR: whisper not installed. Run:  pip install openai-whisper")
        sys.exit(1)

    print(f"[1/3] Loading Whisper model '{model_size}' …")
    model = whisper.load_model(model_size)

    print(f"[2/3] Transcribing '{audio_path}' …  (this may take a minute)")
    result = model.transcribe(audio_path, verbose=False)
    transcript = result["text"].strip()

    print(f"      Done — {len(transcript.split()):,} words transcribed.")
    return transcript


def generate_notes(transcript: str, api_key: str | None) -> str:
    """Send transcript to Gemini and get back structured notes."""
    try:
        import google.generativeai as genai
    except ImportError:
        print("ERROR: google-generativeai not installed. Run:  pip install google-generativeai")
        sys.exit(1)

    import os
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("ERROR: No Gemini API key found. Set GEMINI_API_KEY or pass --api-key.")
        print("       Get a free key at: https://aistudio.google.com")
        sys.exit(1)

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    print("[3/3] Generating notes with Gemini …")

    prompt = f"""You are an expert note-taker. Below is a transcript of a class lecture.
Produce comprehensive, well-structured notes in Markdown. Include exactly these five sections:

1. **Summary** — 3–5 sentence overview of the entire lecture.
2. **Key Points** — Bullet list of the most important concepts, facts, and arguments.
3. **Headings & Sections** — Re-organise the lecture content into clearly labelled sections with sub-bullets. Use ## for main headings and ### for sub-headings.
4. **Glossary** — A definition list of every technical term, proper noun, or concept introduced. Format: **term** — definition.
5. **Review Questions** — 5–8 questions a student could use to test their understanding.

Keep the notes factual and grounded in the transcript. Do not invent content.

---
TRANSCRIPT:
{transcript}
"""

    response = model.generate_content(prompt)
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
        "--api-key",
        default=None,
        help="Gemini API key (default: reads GEMINI_API_KEY env var)",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"ERROR: File not found: {audio_path}")
        sys.exit(1)

    stem = audio_path.stem
    transcript_path = stem + "_transcript.txt"
    output_path = args.output or stem + "_notes.md"

    transcript = transcribe(str(audio_path), args.model)
    save_transcript(transcript, transcript_path)
    notes = generate_notes(transcript, args.api_key)
    save_notes(notes, output_path)

    print("\n── Preview (first 600 chars) ──────────────────────────────────")
    print(notes[:600])
    print("…")


if __name__ == "__main__":
    main()