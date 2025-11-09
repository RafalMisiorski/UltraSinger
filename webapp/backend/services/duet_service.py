"""Duet processing service using speaker diarization and audio separation"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Tuple, List, Dict, Optional, Callable
import re

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading heavy libraries at startup
_pyannote_pipeline = None
_pydub_loaded = False


def _load_pyannote():
    """Lazy load pyannote.audio pipeline"""
    global _pyannote_pipeline
    if _pyannote_pipeline is None:
        try:
            from pyannote.audio import Pipeline

            # Check for HuggingFace token in environment
            hf_token = os.environ.get("HUGGINGFACE_TOKEN")
            if not hf_token:
                logger.warning(
                    "HUGGINGFACE_TOKEN not set. Speaker diarization will fail. "
                    "Get free token at: https://huggingface.co/settings/tokens"
                )
                return None

            _pyannote_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            logger.info("Loaded pyannote speaker diarization pipeline")
        except Exception as e:
            logger.error(f"Failed to load pyannote pipeline: {e}")
            return None

    return _pyannote_pipeline


def _load_pydub():
    """Lazy load pydub"""
    global _pydub_loaded
    if not _pydub_loaded:
        try:
            from pydub import AudioSegment
            _pydub_loaded = True
            logger.info("Loaded pydub for audio manipulation")
        except Exception as e:
            logger.error(f"Failed to load pydub: {e}")
            return False
    return True


async def detect_speakers(
    audio_file: Path,
    min_speakers: int = 2,
    max_speakers: int = 2,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Optional[Dict[str, List[Dict[str, float]]]]:
    """
    Detect and separate speakers in audio file using pyannote.audio

    Args:
        audio_file: Path to audio file
        min_speakers: Minimum number of speakers to detect
        max_speakers: Maximum number of speakers to detect
        progress_callback: Optional callback for progress updates

    Returns:
        Dictionary mapping speaker IDs to list of segments with start/end times
        Example: {
            'SPEAKER_00': [{'start': 0.5, 'end': 5.2}, {'start': 10.1, 'end': 15.3}],
            'SPEAKER_01': [{'start': 5.5, 'end': 9.8}, {'start': 15.5, 'end': 20.0}]
        }
        Returns None if diarization fails or less than min_speakers detected
    """
    try:
        if progress_callback:
            progress_callback("Loading speaker detection model...")

        pipeline = _load_pyannote()
        if pipeline is None:
            logger.error("Pyannote pipeline not available")
            return None

        if progress_callback:
            progress_callback("Analyzing speakers in audio...")

        # Run diarization in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        diarization = await loop.run_in_executor(
            None,
            lambda: pipeline(str(audio_file), num_speakers=max_speakers)
        )

        # Group segments by speaker
        speaker_segments: Dict[str, List[Dict[str, float]]] = {}

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            if speaker not in speaker_segments:
                speaker_segments[speaker] = []

            speaker_segments[speaker].append({
                'start': float(turn.start),
                'end': float(turn.end),
                'duration': float(turn.end - turn.start)
            })

        # Validate we found enough distinct speakers
        num_speakers = len(speaker_segments)
        logger.info(f"Detected {num_speakers} distinct speakers")

        if num_speakers < min_speakers:
            logger.warning(
                f"Only detected {num_speakers} speakers, need at least {min_speakers}. "
                "This may be a solo song."
            )
            return None

        # Calculate speaking time for each speaker
        for speaker, segments in speaker_segments.items():
            total_time = sum(seg['duration'] for seg in segments)
            logger.info(f"{speaker}: {len(segments)} segments, {total_time:.1f}s total")

        # Check if second speaker has enough content (at least 10% of song)
        speakers_sorted = sorted(
            speaker_segments.items(),
            key=lambda x: sum(seg['duration'] for seg in x[1]),
            reverse=True
        )

        if len(speakers_sorted) >= 2:
            main_time = sum(seg['duration'] for seg in speakers_sorted[0][1])
            second_time = sum(seg['duration'] for seg in speakers_sorted[1][1])
            ratio = second_time / max(main_time, 1)

            if ratio < 0.1:  # Second speaker less than 10%
                logger.warning(
                    f"Second speaker only has {ratio*100:.1f}% of vocal time. "
                    "May not be a true duet."
                )
                # Still return results, but log the warning

        if progress_callback:
            progress_callback(f"Detected {num_speakers} speakers successfully")

        return speaker_segments

    except Exception as e:
        logger.error(f"Speaker diarization failed: {e}", exc_info=True)
        return None


async def split_by_speaker(
    audio_file: Path,
    speaker_segments: Dict[str, List[Dict[str, float]]],
    output_dir: Path,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Optional[Tuple[Path, Path]]:
    """
    Split audio into separate files for each speaker

    Args:
        audio_file: Original audio file
        speaker_segments: Speaker segments from detect_speakers()
        output_dir: Directory to save split files
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (speaker_1_file, speaker_2_file) or None if failed
    """
    try:
        if not _load_pydub():
            logger.error("Pydub not available")
            return None

        from pydub import AudioSegment

        if progress_callback:
            progress_callback("Loading audio file...")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Load audio in thread pool
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            lambda: AudioSegment.from_file(str(audio_file))
        )

        # Get the two speakers with most speaking time
        speakers_sorted = sorted(
            speaker_segments.items(),
            key=lambda x: sum(seg['duration'] for seg in x[1]),
            reverse=True
        )[:2]

        if len(speakers_sorted) < 2:
            logger.error("Need at least 2 speakers")
            return None

        speaker_1_id, speaker_1_segments = speakers_sorted[0]
        speaker_2_id, speaker_2_segments = speakers_sorted[1]

        if progress_callback:
            progress_callback(f"Extracting {speaker_1_id} vocal track...")

        # Extract segments for speaker 1
        speaker_1_parts = []
        for segment in sorted(speaker_1_segments, key=lambda x: x['start']):
            start_ms = int(segment['start'] * 1000)
            end_ms = int(segment['end'] * 1000)
            speaker_1_parts.append(audio[start_ms:end_ms])

        if progress_callback:
            progress_callback(f"Extracting {speaker_2_id} vocal track...")

        # Extract segments for speaker 2
        speaker_2_parts = []
        for segment in sorted(speaker_2_segments, key=lambda x: x['start']):
            start_ms = int(segment['start'] * 1000)
            end_ms = int(segment['end'] * 1000)
            speaker_2_parts.append(audio[start_ms:end_ms])

        # Combine parts with small silences between segments
        silence = AudioSegment.silent(duration=100)  # 100ms silence

        if progress_callback:
            progress_callback("Combining segments for speaker 1...")

        if speaker_1_parts:
            speaker_1_audio = speaker_1_parts[0]
            for part in speaker_1_parts[1:]:
                speaker_1_audio = speaker_1_audio + silence + part
        else:
            speaker_1_audio = AudioSegment.silent(duration=1000)

        if progress_callback:
            progress_callback("Combining segments for speaker 2...")

        if speaker_2_parts:
            speaker_2_audio = speaker_2_parts[0]
            for part in speaker_2_parts[1:]:
                speaker_2_audio = speaker_2_audio + silence + part
        else:
            speaker_2_audio = AudioSegment.silent(duration=1000)

        # Save files
        speaker_1_file = output_dir / "speaker_1_vocals.wav"
        speaker_2_file = output_dir / "speaker_2_vocals.wav"

        if progress_callback:
            progress_callback("Saving separated vocal tracks...")

        # Export in thread pool
        await loop.run_in_executor(
            None,
            lambda: speaker_1_audio.export(str(speaker_1_file), format="wav")
        )
        await loop.run_in_executor(
            None,
            lambda: speaker_2_audio.export(str(speaker_2_file), format="wav")
        )

        logger.info(f"Created speaker files: {speaker_1_file}, {speaker_2_file}")

        if progress_callback:
            progress_callback("Vocal separation complete")

        return speaker_1_file, speaker_2_file

    except Exception as e:
        logger.error(f"Failed to split by speaker: {e}", exc_info=True)
        return None


async def merge_to_duet_format(
    speaker_1_txt: Path,
    speaker_2_txt: Path,
    speaker_segments: Dict[str, List[Dict[str, float]]],
    output_file: Path,
    speaker_1_name: str = "Player 1",
    speaker_2_name: str = "Player 2",
    progress_callback: Optional[Callable[[str], None]] = None
) -> Optional[Path]:
    """
    Merge two UltraStar .txt files into duet format with P1/P2 markers

    Args:
        speaker_1_txt: UltraStar file for speaker 1
        speaker_2_txt: UltraStar file for speaker 2
        speaker_segments: Original speaker timing information
        output_file: Path for output duet file
        speaker_1_name: Name for player 1
        speaker_2_name: Name for player 2
        progress_callback: Optional callback for progress updates

    Returns:
        Path to created duet file or None if failed
    """
    try:
        if progress_callback:
            progress_callback("Reading generated UltraStar files...")

        # Read both files
        with open(speaker_1_txt, 'r', encoding='utf-8') as f:
            p1_lines = f.readlines()

        with open(speaker_2_txt, 'r', encoding='utf-8') as f:
            p2_lines = f.readlines()

        # Separate headers and note lines
        p1_headers = {}
        p1_notes = []

        for line in p1_lines:
            if line.startswith('#'):
                # Parse header
                match = re.match(r'#(\w+):(.+)', line.strip())
                if match:
                    p1_headers[match.group(1)] = match.group(2).strip()
            elif line.strip() and line[0] in (':', '*', 'F', '-', 'E'):
                p1_notes.append(line)

        p2_notes = []
        for line in p2_lines:
            if not line.startswith('#') and line.strip() and line[0] in (':', '*', 'F', '-', 'E'):
                p2_notes.append(line)

        if progress_callback:
            progress_callback("Building duet file...")

        # Build duet file
        duet_lines = []

        # Add headers from P1
        duet_lines.append(f"#TITLE:{p1_headers.get('TITLE', 'Unknown')}\n")
        duet_lines.append(f"#ARTIST:{p1_headers.get('ARTIST', 'Unknown')}\n")

        # Add duet-specific headers
        duet_lines.append(f"#DUETSINGERP1:{speaker_1_name}\n")
        duet_lines.append(f"#DUETSINGERP2:{speaker_2_name}\n")

        # Add other important headers
        for header, value in p1_headers.items():
            if header not in ('TITLE', 'ARTIST'):
                duet_lines.append(f"#{header}:{value}\n")

        duet_lines.append("\n")

        # Add P1 section
        duet_lines.append("P1\n")
        for line in p1_notes:
            if not line.startswith('E'):
                duet_lines.append(line)

        # Add P2 section
        duet_lines.append("\nP2\n")
        for line in p2_notes:
            if not line.startswith('E'):
                duet_lines.append(line)

        # TODO: Detect P3 (overlapping vocals) - for future enhancement
        # This would require analyzing the original speaker_segments for overlaps

        # Add end marker
        duet_lines.append("\nE\n")

        if progress_callback:
            progress_callback("Saving duet file...")

        # Write duet file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(duet_lines)

        logger.info(f"Created duet file: {output_file}")

        if progress_callback:
            progress_callback("Duet file created successfully")

        return output_file

    except Exception as e:
        logger.error(f"Failed to merge to duet format: {e}", exc_info=True)
        return None


async def validate_duet_capability(audio_file: Path) -> Tuple[bool, str]:
    """
    Quick check if an audio file is suitable for duet processing

    Returns:
        (is_suitable, message)
    """
    try:
        # Quick diarization check
        pipeline = _load_pyannote()
        if pipeline is None:
            return False, "Speaker detection not available (missing HUGGINGFACE_TOKEN)"

        # Run quick diarization
        loop = asyncio.get_event_loop()
        diarization = await loop.run_in_executor(
            None,
            lambda: pipeline(str(audio_file), num_speakers=2)
        )

        # Count speakers
        speakers = set()
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speakers.add(speaker)

        if len(speakers) < 2:
            return False, f"Only detected {len(speakers)} speaker(s). This appears to be a solo song."

        return True, f"Detected {len(speakers)} speakers - suitable for duet"

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False, f"Validation error: {str(e)}"
