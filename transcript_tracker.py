from pathlib import Path
from typing import Dict, List
import json
import sys
import argparse
import glob

parser = argparse.ArgumentParser(
    description="CLI utility for centralizing media for transcription purposes"
)
parser.add_argument(
    "-m", "--move", action="store_true", help="move files (default: list moves only)"
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
TRANSCRIBE_DIR = "./TRANSCRIBE/"


class MediaFile:
    path: Path
    ready_to_return: bool
    needs_transcription: bool

    def __init__(self, path: Path):
        self.path = path
        self.needs_transcription = not self._has_srt() or not self._has_txt()

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
        if filepath.suffix not in MEDIA_EXTENSIONS:
            return None
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

    def save(self):
        self._save_records()

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
        self.scan_root_directory = Path(directory)
        self._walk()

    def _is_in_transcribe_dir(self, media_file: MediaFile):
        return media_file.path.parent == self.transcribe_queue_dir

    def _walk(self):
        files = Path(self.scan_root_directory).rglob("*")
        for file in files:
            if file.parent == self.scan_root_directory:
                continue
            media_file = MediaFile.get_instance_if_media_file(file)
            if not media_file:
                continue
            if media_file.needs_transcription:
                if not self._is_in_transcribe_dir(media_file):
                    records.add_file(media_file)
                    new_filepath = self.transcribe_queue_dir / media_file.path.name
                    print(
                        f">>> Queueing {media_file.path.name} in {self.transcribe_queue_dir.name}"
                    )
                    if args.move:
                        media_file.path.rename(new_filepath)
            elif not media_file.needs_transcription:
                if self._is_in_transcribe_dir(media_file):
                    orig_dir = Path(records.get_original_dir(media_file))
                    pattern = glob.escape(media_file.path.stem) + ".*"
                    files_to_return = self.transcribe_queue_dir.glob(pattern)
                    for finished_file in files_to_return:
                        new_filepath = orig_dir / finished_file.name
                        if new_filepath.exists():
                            continue
                        print(f"=== Moving {finished_file.name} to {orig_dir.name}")
                        if args.move:
                            finished_file.rename(new_filepath)

        if not args.move:
            message = "This was a demonstration. Nothing was moved.\n"
            message += f"{RECORDS_FILE} and {TRANSCRIBE_DIR} were created if they did not already exist."
            print(message)


if __name__ == "__main__":

    scanner = MediaGrabber()
    records.save()
