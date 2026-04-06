# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Audio utilities for LiveKit hotel assistant.

This module provides functions to read raw audio files and convert them to
AsyncIterator[AudioFrame] for use with LiveKit agents.
"""

import os
from collections.abc import AsyncIterator

from livekit.rtc import AudioFrame


async def read_asset_audio(
    filename: str,
    sample_rate: int = 44100,
    num_channels: int = 1,
    chunk_size: int = 1024,
) -> AsyncIterator[AudioFrame]:
    """
    Read a raw audio file from the assets directory and yield AudioFrame objects.

    Args:
        filename: Name of the audio file in the assets directory
        sample_rate: Sample rate in Hz (default: 44100)
        num_channels: Number of audio channels (default: 1 for mono)
        chunk_size: Number of samples per chunk (default: 1024)

    Yields:
        AudioFrame: Audio frames suitable for LiveKit playback

    Raises:
        FileNotFoundError: If the audio file is not found
        RuntimeError: If there's an error reading the file
    """
    # Get the path to the audio file in assets directory
    current_dir = os.path.dirname(__file__)
    audio_path = os.path.join(current_dir, "assets", filename)

    try:
        with open(audio_path, "rb") as audio_file:
            while True:
                # Read chunk_size * num_channels * 2 bytes (16-bit = 2 bytes per sample)
                chunk_data = audio_file.read(chunk_size * num_channels * 2)

                if not chunk_data:
                    break

                # Calculate actual samples per channel based on data read
                actual_samples = len(chunk_data) // (num_channels * 2)

                if actual_samples > 0:
                    # Create AudioFrame with the chunk data
                    audio_frame = AudioFrame(
                        data=chunk_data,
                        sample_rate=sample_rate,
                        num_channels=num_channels,
                        samples_per_channel=actual_samples,
                    )

                    yield audio_frame

    except FileNotFoundError as e:
        raise FileNotFoundError(f"Audio file '{filename}' not found in assets directory") from e
    except Exception as e:
        raise RuntimeError(f"Error reading audio file '{filename}': {e}") from e


# Convenience functions for specific audio files
async def greeting_audio() -> AsyncIterator[AudioFrame]:
    """
    Read the greeting.raw audio file and yield AudioFrame objects.

    The greeting.raw file is mono 44100Hz 16-bit PCM audio.

    Yields:
        AudioFrame: Audio frames suitable for LiveKit playback
    """
    async for frame in read_asset_audio("greeting.raw"):
        yield frame


async def un_momento_audio() -> AsyncIterator[AudioFrame]:
    """
    Read the un_momento.raw audio file and yield AudioFrame objects.

    The un_momento.raw file is mono 44100Hz 16-bit PCM audio.

    Yields:
        AudioFrame: Audio frames suitable for LiveKit playback
    """
    async for frame in read_asset_audio("un_momento.raw"):
        yield frame
