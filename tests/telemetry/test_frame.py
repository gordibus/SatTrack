import pytest

from satrx.telemetry.frame import (
    TelemetryParameterSpec,
    decode_telemetry_frame,
    extract_parameter,
    extract_raw_bits,
)


class TestExtractRawBits:

    def test_nominal_case_crossing_byte_boundary(self):
        buf = bytes([0b10110100, 0b11001010])

        value = extract_raw_bits(buf, bit_offset=2, bit_length=5)

        assert value == 0b11010

    def test_nominal_case_whole_byte(self):
        buf = bytes([0xA5])

        assert extract_raw_bits(buf, bit_offset=0, bit_length=8) == 0xA5

    def test_edge_case_out_of_bounds(self):
        with pytest.raises(ValueError):
            extract_raw_bits(bytes([0x00]), bit_offset=4, bit_length=8)

    def test_edge_case_invalid_bit_length(self):
        with pytest.raises(ValueError):
            extract_raw_bits(bytes([0x00]), bit_offset=0, bit_length=0)


class TestTelemetryParameterSpec:

    def test_nominal_case(self):
        spec = TelemetryParameterSpec(name="temp_cpu", bit_offset=0, bit_length=8, scale=0.5, offset=-20.0)
        assert spec.name == "temp_cpu"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"name": "  "},
            {"bit_offset": -1},
            {"bit_length": 0},
        ],
    )
    def test_edge_case_invalid_input(self, kwargs):
        defaults = {"name": "temp_cpu", "bit_offset": 0, "bit_length": 8}
        defaults.update(kwargs)
        with pytest.raises(ValueError):
            TelemetryParameterSpec(**defaults)


class TestExtractParameterAndDecodeFrame:

    def test_nominal_case_scale_and_offset_applied(self):
        buf = bytes([100])
        spec = TelemetryParameterSpec(name="temp", bit_offset=0, bit_length=8, scale=0.5, offset=-20.0)

        value = extract_parameter(buf, spec)

        assert value == pytest.approx(100 * 0.5 - 20.0)

    def test_edge_case_empty_specs(self):
        with pytest.raises(ValueError):
            decode_telemetry_frame(bytes([1, 2, 3]), [])

    def test_interop_multiple_parameters_from_same_buffer(self):
        # buffer de 2 octets : temp (8 bits, brut=100) | flag (1 bit) | counter (7 bits, brut=42)
        buf = bytes([100, (1 << 7) | 42])
        specs = [
            TelemetryParameterSpec(name="temp", bit_offset=0, bit_length=8, scale=0.5, offset=-20.0, unit="C"),
            TelemetryParameterSpec(name="flag", bit_offset=8, bit_length=1),
            TelemetryParameterSpec(name="counter", bit_offset=9, bit_length=7),
        ]

        result = decode_telemetry_frame(buf, specs)

        assert result["temp"] == pytest.approx(30.0)
        assert result["flag"] == 1.0
        assert result["counter"] == 42.0
