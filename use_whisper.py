import re
from pathlib import Path
import argparse
import sys
import time
import subprocess
import json
import whisper
import torch

# TODO: wait for M1/M2 support in PyTorch to mature.

# DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
DEVICE = "cpu"

parser = argparse.ArgumentParser(
    description="CLI utility for generating subtitles and transcripts for media"
)
model_list = whisper.available_models()
parser.add_argument(
    "-m",
    "--model",
    nargs="?",
    help=f"choose whisper model ({", ".join(model_list)})",
    default="large-v3",
)
parser.add_argument(
    "-i", "--input", nargs="+", required=True, help="input file or directory"
)
args = parser.parse_args()


model = whisper.load_model(args.model, device=DEVICE)


def write_srt(result, filepath: Path):
    if filepath.suffix != ".srt":
        filepath = filepath.parent / (filepath.stem + ".srt")
    with filepath.open("w", encoding="utf-8") as f:
        for i, segment in enumerate(result["segments"]):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = normalize_text(segment["text"])
            f.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")


def format_timestamp(seconds):
    millis = int((seconds % 1) * 1000)
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def normalize_text(text):
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,\.!\?;:])", r"\1", text)
    return text


def write_txt(result, filepath: Path, pause_threshold=2.0):
    if filepath.suffix != ".txt":
        filepath = filepath.parent / (filepath.stem + ".txt")
    with filepath.open("w", encoding="utf-8") as f:
        current_paragraph = []
        for i, segment in enumerate(result["segments"]):
            current_paragraph.append(normalize_text(segment["text"]))

            if (
                i + 1 < len(result["segments"])
                and result["segments"][i + 1]["start"] - segment["end"]
                > pause_threshold
            ):
                f.write(" ".join(current_paragraph) + "\n\n")
                current_paragraph = []

        if current_paragraph:
            f.write(" ".join(current_paragraph) + "\n")


WHISPER_FORMATS = {
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".ogg",
    ".opus",
    ".wma",
}


def process_file(filepath: Path):
    if not filepath.exists():
        return
    if filepath.suffix not in WHISPER_FORMATS:
        return
    srt = filepath.parent / (filepath.stem + ".srt")
    txt = filepath.parent / (filepath.stem + ".txt")
    if srt.exists() and txt.exists():
        return
    audio_duration = get_audio_duration_ffprobe(filepath)
    print(f"=== Processing {filepath} ({audio_duration})")
    start_time = time.time()
    result = model.transcribe(str(filepath), fp16=False)
    transcribe_time = time.time() - start_time
    ratio = audio_duration / transcribe_time
    print(
        f"Transcription took {transcribe_time:.2f}s for {audio_duration:.2f}s audio (ratio: {ratio:.2f}x)"
    )

    print(f"=== Writing SRT and TXT files for {filepath.name}")
    write_txt(result, filepath)
    write_srt(result, filepath)


def process(filepath: Path):
    if filepath.is_dir():
        print(f">>> Looking in {filepath} for files")
        dir_glob = filepath.glob("*")
        for p in dir_glob:
            if p.is_dir():
                continue
            process_file(p)
    else:
        process_file(filepath)


def get_audio_duration_ffprobe(filepath):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            filepath,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def main():
    for path in args.input:
        process(Path(path))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(1)
