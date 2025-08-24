from pathlib import Path
from typing import Dict, List
import json
import sys
import argparse
import glob
import subprocess

parser = argparse.ArgumentParser(
    description="CLI utility for centralizing media for transcription purposes"
)
parser.add_argument(
    "-m", "--move", action="store_true", help="move files (default: list moves only)"
)

imports = parser.add_mutually_exclusive_group()
imports.add_argument(
    "-I",
    "--skip-import",
    action="store_true",
    help="skip import, move out of transcribe directory only",
)
imports.add_argument(
    "-i",
    "--import-only",
    action="store_true",
    help="import only; skip checking transcription directory",
)

audio_check = parser.add_mutually_exclusive_group()
audio_check.add_argument(
    "-A", "--no-audio-check", action="store_true", help="skip audio check; much faster"
)
audio_check.add_argument(
    "-c",
    "--cleanup",
    action="store_true",
    help="return files with missing audio to source directory",
)
parser.add_argument(
    "-C",
    "--check-records",
    action="store_true",
    help="check if all files in TRANSCRIBE have records",
)

args = parser.parse_args()

MEDIA_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".mp3",
    ".wav",
    ".m4a",
    ".opus",
}
RECORDS_FILE = "records.json"
TRANSCRIBE_DIR_NAME = "TRANSCRIBE"
TRANSCRIBE_DIR = f"./{TRANSCRIBE_DIR_NAME}/"


class MediaFile:
    path: Path
    ready_to_return: bool
    needs_transcription: bool
    has_audio: bool

    def __init__(self, path: Path, has_audio: bool = True):
        self.path = path
        self.needs_transcription = not self._has_srt() or not self._has_txt()
        self.has_audio = has_audio

    @staticmethod
    def check_file_for_audio(filepath: Path):
        if args.no_audio_check:
            return True
        if args.check_records:
            return True
        if not filepath.exists():
            return False
        cmd_line = "ffprobe -loglevel error -select_streams a -show_entries stream=codec_type -of csv=p=0"
        cmd = cmd_line.split()
        cmd += [str(filepath)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip() == "audio"

    def _get_path_with_ext(self, ext: str):
        if not ext.startswith("."):
            ext = f".{ext}"
        return self.path.parent / (self.path.stem + ext)

    def _has_srt(self):
        srt_path = self._get_path_with_ext("srt")
        return srt_path.exists()

    def _has_txt(self):
        txt_path = self._get_path_with_ext("txt")
        return txt_path.exists()

    def get_record(self):
        return {self.path.stem: str(self.path.parent)}

    @staticmethod
    def get_instance_if_media_file(filepath: Path):
        if filepath.suffix.lower() not in MEDIA_EXTENSIONS:
            return None
        if filepath.parent.name != TRANSCRIBE_DIR_NAME:
            extensions = [".srt", ".txt"]
            has_transcripts = all(
                (filepath.parent / (filepath.stem + ext)).exists() for ext in extensions
            )
            if has_transcripts:
                return None
        if not MediaFile.check_file_for_audio(filepath):
            return MediaFile(filepath, has_audio=False)
        return MediaFile(filepath)


class RecordsManager:
    # {file_base_name: original_parent_directory}
    records_file = Path(RECORDS_FILE)
    records: Dict[str, str] = {}

    def __init__(self):
        self._load_records()

    def _load_records(self):
        if not self.records_file.exists():
            return {}
        with self.records_file.open("r", encoding="utf-8") as f:
            self.records = json.load(f)

    def _save_records(self):
        with self.records_file.open("w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2)

    def add_file(self, media_file: MediaFile):
        if media_file.path.stem not in self.records:
            self.records.update(media_file.get_record())
            self._save_records()

    def has_record(self, media_file: MediaFile) -> bool:
        return self.records.get(glob.escape(media_file.path.stem), None) is not None

    def get_original_dir(self, media_file: MediaFile):
        if media_file.path.stem not in self.records:
            raise KeyError(
                f"Base filename for {media_file.path.name} not in {RECORDS_FILE}"
            )
        record = self.records.get(media_file.path.stem)
        if record:
            return record
        sys.exit(1)


records = RecordsManager()


class MediaGrabber:
    transcription_needs: List[MediaFile] = []
    transcribe_queue_dir = Path(TRANSCRIBE_DIR)

    def __init__(self, directory: str = "."):
        if not self.transcribe_queue_dir.exists():
            self.transcribe_queue_dir.mkdir(exist_ok=True)
        dirpath = Path(directory)
        if dirpath.name != TRANSCRIBE_DIR_NAME:
            self.scan_root_directory = dirpath
            self._walk()

    def _is_in_transcribe_dir(self, media_file: MediaFile):
        return media_file.path.parent.absolute() == self.transcribe_queue_dir.absolute()

    def _glob_move_files(self, media_file: MediaFile, dest_dir: Path):
        pattern = glob.escape(media_file.path.stem) + ".*"
        files_to_move = media_file.path.parent.glob(pattern)
        for file_to_move in files_to_move:
            if not file_to_move.exists():
                continue
            if file_to_move.is_dir():
                print(f"{file_to_move} is a directory!?")
                continue
            new_filepath = dest_dir / file_to_move.name
            if new_filepath.exists():
                print(f"### {new_filepath} exists, skipping")
                continue
            print(f"=== Moving {file_to_move} to {dest_dir}")
            if args.move:
                file_to_move.rename(new_filepath)

    def _walk(self):
        files = Path(self.scan_root_directory).rglob("*")
        for file in files:
            if file.parent == self.scan_root_directory:
                continue
            media_file = MediaFile.get_instance_if_media_file(file)
            if not media_file:
                continue
            if not media_file.has_audio:
                continue
            if self._is_in_transcribe_dir(media_file):
                # if the file is missing records, move it into a child directory.
                if not records.has_record(media_file):
                    new_dir = media_file.path.parent / "find_original_dir"
                    new_dir.mkdir(exist_ok=True)
                    self._glob_move_files(media_file, new_dir)
                    continue
                if args.import_only:
                    continue
                if args.cleanup:
                    if not media_file.has_audio:
                        dest = Path(records.get_original_dir(media_file))
                        self._glob_move_files(media_file, dest)
                        continue
                if not media_file.needs_transcription:
                    orig_dir = Path(records.get_original_dir(media_file))
                    self._glob_move_files(media_file, orig_dir)
            # leave other transcription projects in place
            if TRANSCRIBE_DIR_NAME in str(media_file.path):
                continue
            if args.skip_import:
                continue
            if media_file.needs_transcription:
                records.add_file(media_file)
                self._glob_move_files(media_file, self.transcribe_queue_dir)

        if not args.move:
            message = "This was a demonstration. Nothing was moved.\n"
            message += f"{RECORDS_FILE} and {TRANSCRIBE_DIR} were created if they did not already exist."
            print(message)


if __name__ == "__main__":
    try:
        if Path(".").absolute().name == TRANSCRIBE_DIR_NAME:
            print("CWD is a transcription directory. Please try the parent directory.")
            sys.exit(1)
        scanner = MediaGrabber()
    except KeyboardInterrupt:
        print()
        sys.exit(1)
