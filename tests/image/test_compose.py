import numpy as np
import pytest

from satrx.image.compose import (
    METEOR_LRPT_APID_CHANNELS,
    align_channel_heights,
    compose_from_channel_map,
    compose_rgb,
    normalize_channel,
)


class TestMeteorLrptApidChannels:

    def test_nominal_case_known_apids_present(self):
        assert set(METEOR_LRPT_APID_CHANNELS) == {64, 65, 66, 67, 68}
        assert 70 not in METEOR_LRPT_APID_CHANNELS  # telemetrie, pas un canal image
        assert "visible" in METEOR_LRPT_APID_CHANNELS[64]


class TestAlignChannelHeights:

    def test_nominal_case_truncates_to_min_height(self):
        tall = np.zeros((10, 5), dtype=np.uint16)
        short = np.zeros((7, 5), dtype=np.uint16)

        aligned = align_channel_heights([tall, short])

        assert aligned[0].shape[0] == 7
        assert aligned[1].shape[0] == 7

    def test_edge_case_empty_channel_list(self):
        with pytest.raises(ValueError):
            align_channel_heights([])

    def test_edge_case_zero_height_channel(self):
        with pytest.raises(ValueError):
            align_channel_heights([np.zeros((0, 5), dtype=np.uint16)])


class TestNormalizeChannel:

    def test_nominal_case_stretches_to_full_range(self):
        channel = np.array([[0, 50, 100]], dtype=np.uint16)

        normalized = normalize_channel(channel, low_percentile=0.0, high_percentile=100.0)

        assert normalized.dtype == np.uint8
        assert normalized[0, 0] == 0
        assert normalized[0, 2] == 255

    def test_edge_case_invalid_percentiles(self):
        channel = np.array([[0, 50, 100]], dtype=np.uint16)

        with pytest.raises(ValueError):
            normalize_channel(channel, low_percentile=90.0, high_percentile=10.0)

    def test_edge_case_flat_channel_returns_zeros(self):
        channel = np.full((4, 4), 42, dtype=np.uint16)

        normalized = normalize_channel(channel)

        assert np.all(normalized == 0)


class TestComposeRgb:

    def test_nominal_case_shape_and_dtype(self):
        red = np.random.randint(0, 4096, size=(20, 10), dtype=np.uint16)
        green = np.random.randint(0, 4096, size=(20, 10), dtype=np.uint16)
        blue = np.random.randint(0, 4096, size=(20, 10), dtype=np.uint16)

        image = compose_rgb(red, green, blue)

        assert image.shape == (20, 10, 3)
        assert image.dtype == np.uint8

    def test_edge_case_mismatched_dimensions_are_cropped(self):
        red = np.zeros((20, 10), dtype=np.uint16)
        green = np.zeros((18, 12), dtype=np.uint16)
        blue = np.zeros((25, 8), dtype=np.uint16)

        image = compose_rgb(red, green, blue)

        assert image.shape == (18, 8, 3)

    def test_interop_without_normalization_preserves_raw_values(self):
        red = np.array([[10, 20]], dtype=np.uint16)
        green = np.array([[30, 40]], dtype=np.uint16)
        blue = np.array([[50, 60]], dtype=np.uint16)

        image = compose_rgb(red, green, blue, normalize=False)

        assert image[0, 0].tolist() == [10, 30, 50]
        assert image[0, 1].tolist() == [20, 40, 60]


class TestComposeFromChannelMap:

    def test_nominal_case(self):
        channels = {
            64: np.random.randint(0, 4096, size=(15, 8), dtype=np.uint16),
            65: np.random.randint(0, 4096, size=(15, 8), dtype=np.uint16),
            66: np.random.randint(0, 4096, size=(15, 8), dtype=np.uint16),
        }

        image = compose_from_channel_map(channels, red_apid=66, green_apid=65, blue_apid=64)

        assert image.shape == (15, 8, 3)
        assert image.dtype == np.uint8

    def test_edge_case_missing_apid(self):
        channels = {64: np.zeros((10, 5), dtype=np.uint16), 65: np.zeros((10, 5), dtype=np.uint16)}

        with pytest.raises(ValueError, match="66"):
            compose_from_channel_map(channels, red_apid=66, green_apid=65, blue_apid=64)

    def test_interop_matches_compose_rgb(self):
        red = np.array([[1, 2]], dtype=np.uint16)
        green = np.array([[3, 4]], dtype=np.uint16)
        blue = np.array([[5, 6]], dtype=np.uint16)
        channels = {64: blue, 65: green, 66: red}

        via_map = compose_from_channel_map(
            channels, red_apid=66, green_apid=65, blue_apid=64, normalize=False
        )
        direct = compose_rgb(red, green, blue, normalize=False)

        assert np.array_equal(via_map, direct)
