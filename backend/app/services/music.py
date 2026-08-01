"""Müzik üretimi — Meta MusicGen stub."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from app.config import get_settings


async def generate_music(
    out_path: Path,
    description: str,
    duration_seconds: int = 30,
) -> bool:
    """Müzik oluştur — şu an mock, canlı API placeholder.

    Real: Meta MusicGen API, Riffusion, Jukebox vb.
    Mock: 0.5-1.0 sn sessiz MP3 dosyası üret.

    Returns: is_mock
    """
    settings = get_settings()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.mock_ai:
        _write_mock_mp3(out_path, duration_seconds)
        return True

    # TODO: Meta MusicGen API endpoint
    # - API key: MUSICGEN_API_KEY
    # - Prompt: description
    # - Duration: duration_seconds
    # - Output: MP3 file

    _write_mock_mp3(out_path, duration_seconds)
    return True


def _write_mock_mp3(path: Path, duration_seconds: int) -> None:
    """Basit sessiz MP3 — gerçek müzik olmayan placeholder."""
    import struct

    path.parent.mkdir(parents=True, exist_ok=True)

    # Minimal MP3 header + silent frame (MPEG Layer III)
    # ID3v2.3 header + minimal MP3 frames
    mp3_data = bytearray()

    # ID3v2.3 (opsiyonel ama standard)
    mp3_data += b"ID3"  # Identifier
    mp3_data += b"\x03\x00"  # Version 2.3.0
    mp3_data += b"\x00"  # Flags
    mp3_data += b"\x00\x00\x00\x00"  # Size (0)

    # Minimal MPEG Layer III frames — her frame ~26ms
    bitrate = 128  # kbps
    sample_rate = 44100  # Hz
    frame_samples = 1152  # MPEG Layer III
    frame_duration_ms = (frame_samples / sample_rate) * 1000
    num_frames = max(1, int((duration_seconds * 1000) / frame_duration_ms))

    for _ in range(num_frames):
        # MP3 frame header: 0xFFF (sync word) + metadata
        frame_header = 0xFFFB9000  # Sync + MPEG-1 Layer III + minimal flags
        mp3_data += struct.pack(">I", frame_header)
        # Side info + main data (minimal)
        mp3_data += b"\x00" * 117

    path.write_bytes(mp3_data)
