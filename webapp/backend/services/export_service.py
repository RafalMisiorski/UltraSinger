"""Export service for converting UltraStar files to various formats"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class UltraStarParser:
    """Parse UltraStar .txt files"""

    @staticmethod
    def parse_file(file_path: Path) -> Dict:
        """
        Parse UltraStar file and extract metadata + notes

        Returns:
            {
                'metadata': {'TITLE': '...', 'ARTIST': '...', ...},
                'notes': [{'type': ':', 'start': 0, 'duration': 4, 'pitch': 12, 'text': 'Hello'}, ...]
            }
        """
        metadata = {}
        notes = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Metadata lines start with #
                if line.startswith('#'):
                    parts = line[1:].split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        metadata[key.strip()] = value.strip()

                # Note lines: [type] [start_beat] [duration] [pitch] [text]
                elif line[0] in [':', '*', 'F', 'R']:
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        note = {
                            'type': parts[0],
                            'start': int(parts[1]),
                            'duration': int(parts[2]),
                            'pitch': int(parts[3]),
                            'text': parts[4]
                        }
                        notes.append(note)

                # Player change for duets
                elif line.startswith('P'):
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        notes.append({
                            'type': 'P',
                            'player': int(parts[1]),
                            'text': f'[Player {parts[1]}]'
                        })

        return {'metadata': metadata, 'notes': notes}


def convert_to_srt(ultrastar_file: Path) -> str:
    """
    Convert UltraStar file to SRT subtitle format

    Format:
    1
    00:00:00,000 --> 00:00:04,000
    Hello world

    2
    00:00:04,500 --> 00:00:08,000
    This is a test
    """
    data = UltraStarParser.parse_file(ultrastar_file)
    notes = data['notes']
    metadata = data['metadata']

    # Get BPM for timing calculation
    bpm = float(metadata.get('BPM', 120))
    gap = float(metadata.get('GAP', 0))  # milliseconds

    # Convert beat to milliseconds: ms = (beat / BPM * 60 * 1000) + gap
    def beat_to_ms(beat):
        return int((beat / bpm * 60 * 1000) + gap)

    def ms_to_srt_time(ms):
        """Convert milliseconds to SRT time format HH:MM:SS,mmm"""
        hours = int(ms // 3600000)
        minutes = int((ms % 3600000) // 60000)
        seconds = int((ms % 60000) // 1000)
        milliseconds = int(ms % 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    srt_output = []
    subtitle_num = 1

    current_line = []
    line_start = None

    for note in notes:
        if note['type'] == 'P':
            # Player change - flush current line if exists
            if current_line:
                start_ms = beat_to_ms(line_start)
                end_ms = beat_to_ms(current_line[-1]['start'] + current_line[-1]['duration'])
                text = ' '.join([n['text'] for n in current_line])

                srt_output.append(f"{subtitle_num}\n")
                srt_output.append(f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}\n")
                srt_output.append(f"{text}\n\n")
                subtitle_num += 1
                current_line = []
                line_start = None
            continue

        # Regular note
        if line_start is None:
            line_start = note['start']

        current_line.append(note)

        # Check if this is end of line (next note has gap or is last)
        # For simplicity, create subtitle per note or group by proximity
        if len(current_line) >= 5:  # Group ~5 words
            start_ms = beat_to_ms(line_start)
            end_ms = beat_to_ms(note['start'] + note['duration'])
            text = ' '.join([n['text'] for n in current_line])

            srt_output.append(f"{subtitle_num}\n")
            srt_output.append(f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}\n")
            srt_output.append(f"{text}\n\n")
            subtitle_num += 1
            current_line = []
            line_start = None

    # Flush remaining
    if current_line:
        start_ms = beat_to_ms(line_start)
        end_ms = beat_to_ms(current_line[-1]['start'] + current_line[-1]['duration'])
        text = ' '.join([n['text'] for n in current_line])

        srt_output.append(f"{subtitle_num}\n")
        srt_output.append(f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}\n")
        srt_output.append(f"{text}\n\n")

    return ''.join(srt_output)


def convert_to_lrc(ultrastar_file: Path) -> str:
    """
    Convert UltraStar file to LRC lyrics format

    Format:
    [ar:Artist Name]
    [ti:Song Title]
    [00:00.00]Hello world
    [00:04.50]This is a test
    """
    data = UltraStarParser.parse_file(ultrastar_file)
    notes = data['notes']
    metadata = data['metadata']

    # Get BPM for timing
    bpm = float(metadata.get('BPM', 120))
    gap = float(metadata.get('GAP', 0))

    def beat_to_ms(beat):
        return int((beat / bpm * 60 * 1000) + gap)

    def ms_to_lrc_time(ms):
        """Convert milliseconds to LRC time format [MM:SS.xx]"""
        minutes = int(ms // 60000)
        seconds = int((ms % 60000) // 1000)
        centiseconds = int((ms % 1000) // 10)
        return f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]"

    lrc_output = []

    # Add metadata
    if 'ARTIST' in metadata:
        lrc_output.append(f"[ar:{metadata['ARTIST']}]\n")
    if 'TITLE' in metadata:
        lrc_output.append(f"[ti:{metadata['TITLE']}]\n")
    if 'CREATOR' in metadata:
        lrc_output.append(f"[by:{metadata['CREATOR']}]\n")

    lrc_output.append("\n")

    # Add lyrics with timestamps
    current_line = []
    line_start = None

    for note in notes:
        if note['type'] == 'P':
            # Player change - flush and add marker
            if current_line:
                start_ms = beat_to_ms(line_start)
                text = ' '.join([n['text'] for n in current_line])
                lrc_output.append(f"{ms_to_lrc_time(start_ms)}{text}\n")
                current_line = []
                line_start = None
            lrc_output.append(f"{note['text']}\n")
            continue

        if line_start is None:
            line_start = note['start']

        current_line.append(note)

        # Group words (every ~5 words or line break)
        if len(current_line) >= 5:
            start_ms = beat_to_ms(line_start)
            text = ' '.join([n['text'] for n in current_line])
            lrc_output.append(f"{ms_to_lrc_time(start_ms)}{text}\n")
            current_line = []
            line_start = None

    # Flush remaining
    if current_line:
        start_ms = beat_to_ms(line_start)
        text = ' '.join([n['text'] for n in current_line])
        lrc_output.append(f"{ms_to_lrc_time(start_ms)}{text}\n")

    return ''.join(lrc_output)


def convert_to_json(ultrastar_file: Path) -> str:
    """
    Convert UltraStar file to JSON format

    Returns structured JSON with metadata and notes
    """
    data = UltraStarParser.parse_file(ultrastar_file)
    return json.dumps(data, indent=2)


def convert_to_txt(ultrastar_file: Path) -> str:
    """
    Convert UltraStar file to plain text (just lyrics)

    Returns:
        Plain text with just the lyrics
    """
    data = UltraStarParser.parse_file(ultrastar_file)
    notes = data['notes']
    metadata = data['metadata']

    lines = []

    # Add title/artist if available
    if 'TITLE' in metadata:
        lines.append(f"{metadata['TITLE']}")
    if 'ARTIST' in metadata:
        lines.append(f"by {metadata['ARTIST']}")
    if lines:
        lines.append('')  # Blank line

    # Extract just the lyrics
    current_line = []

    for note in notes:
        if note['type'] == 'P':
            if current_line:
                lines.append(' '.join(current_line))
                current_line = []
            lines.append('')
            lines.append(note['text'])
            lines.append('')
            continue

        current_line.append(note['text'])

        # Line break heuristic (every ~10 words)
        if len(current_line) >= 10:
            lines.append(' '.join(current_line))
            current_line = []

    # Flush remaining
    if current_line:
        lines.append(' '.join(current_line))

    return '\n'.join(lines)
