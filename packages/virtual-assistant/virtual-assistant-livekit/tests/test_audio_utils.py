# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Tests for audio utilities.
"""

from unittest.mock import mock_open, patch

import pytest

from virtual_assistant_livekit.audio_utils import read_asset_audio


class TestAudioUtils:
    """Test cases for audio utility functions."""

    @pytest.mark.asyncio
    async def test_read_asset_audio_with_mock_data(self):
        """Test reading asset audio file with mocked data."""
        # Create mock audio data (1024 samples * 1 channel * 2 bytes = 2048 bytes)
        mock_audio_data = b"\x00\x01" * 1024  # 16-bit samples

        with patch("builtins.open", mock_open(read_data=mock_audio_data)):
            frames = []
            async for frame in read_asset_audio("test.raw"):
                frames.append(frame)
                break  # Just test the first frame

            assert len(frames) == 1
            frame = frames[0]
            assert frame.sample_rate == 44100
            assert frame.num_channels == 1
            assert frame.samples_per_channel == 1024

    def test_audio_frame_properties(self):
        """Test that we can create AudioFrame objects with correct properties."""
        from livekit.rtc import AudioFrame

        # Test data: 1024 samples * 1 channel * 2 bytes = 2048 bytes
        test_data = b"\x00\x01" * 1024

        frame = AudioFrame(data=test_data, sample_rate=44100, num_channels=1, samples_per_channel=1024)

        assert frame.sample_rate == 44100
        assert frame.num_channels == 1
        assert frame.samples_per_channel == 1024
        assert frame.duration == pytest.approx(1024 / 44100, rel=1e-6)
