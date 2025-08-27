# Transription Queue

## Purpose

To facilitate queueing and de-queueing of files to run through external transcription tools.

## General Mechanism

Search subdirectories for media files, consider location and the presence of transcription files, and relocate accordingly.

### By Default

- `records.json` is the location for storing original path data for each basename
- The files moved to .TRANSCRIBE/ by this script will have records.json entries
- The next time this script runs in the same directory as the previously created records.json, it will relocate the media files with the desired transcript files (currently: .srt and .txt)

## Usage

In a directory with subdirectories filled with media you wish to transcribe,

`python transcript_tracker.py`

## Ideas for Future

- Hash based records, e.g., [{hash: { stem: stem, origin: original_path }}]
- Rename incoming files to TRANSCRIBE/[sha256sum].[ext]
- Track multiple origins in case of duplicates (copy non-extant hash.\* files back to each origin with correct stem)
- Create an unqueue command that reverses the move to the TRANSCRIBE directory (even if missing transcripts)
- Allow more customizability about desired subtitle types
- Create a secondary script to transcribe the relocated files
- Add the option to transcribe files in place if they lack the desired subtitle files (basically a complete re-write)
- Add image and PDF handling via tesseract / OCRmyPDF type handling
- COMPLETED: Unify \_have_srt and \_have_txt methods
- COMPLETED: Create a move_basename_files_by_glob helper
- DEFER: Centralize records.json and store relative root along with basename and original path data
- DEFER: Centralize TRANSCRIBE directory
