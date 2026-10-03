import numpy as np
import pytest

from satrx.image.dct import (
    STANDARD_LUMINANCE_QUANT_TABLE,
    block_to_zigzag,
    dct_8x8,
    dequantize,
    idct_8x8,
    quantize,
    scale_quantization_table,
    zigzag_to_block,
)


class TestDctIdct:

    def test_nominal_case_roundtrip(self):
        rng = np.random.default_rng(0)
        block = rng.uniform(-100, 100, size=(8, 8))

        coeffs = dct_8x8(block)
        recovered = idct_8x8(coeffs)

        assert np.allclose(recovered, block, atol=1e-9)

    def test_nominal_case_flat_block_has_only_dc_energy(self):
        block = np.full((8, 8), 42.0)

        coeffs = dct_8x8(block)
        ac_coeffs = coeffs.copy()
        ac_coeffs[0, 0] = 0.0

        assert coeffs[0, 0] != 0.0
        assert np.max(np.abs(ac_coeffs)) < 1e-9

    def test_edge_case_wrong_shape(self):
        with pytest.raises(ValueError):
            dct_8x8(np.zeros((4, 4)))
        with pytest.raises(ValueError):
            idct_8x8(np.zeros((8, 9)))


class TestZigzag:

    def test_nominal_case_roundtrip(self):
        rng = np.random.default_rng(1)
        block = rng.uniform(-50, 50, size=(8, 8))

        zz = block_to_zigzag(block)
        recovered = zigzag_to_block(zz)

        assert np.allclose(recovered, block)

    def test_nominal_case_dc_is_first_element(self):
        block = np.arange(64, dtype=np.float64).reshape(8, 8)

        zz = block_to_zigzag(block)

        assert zz[0] == block[0, 0]

    def test_edge_case_wrong_length(self):
        with pytest.raises(ValueError):
            zigzag_to_block([1.0, 2.0, 3.0])

    def test_interop_with_dct(self):
        rng = np.random.default_rng(2)
        block = rng.uniform(-100, 100, size=(8, 8))

        coeffs = dct_8x8(block)
        zz = block_to_zigzag(coeffs)
        recovered_coeffs = zigzag_to_block(zz)
        recovered_block = idct_8x8(recovered_coeffs)

        assert np.allclose(recovered_block, block, atol=1e-9)


class TestDequantize:

    def test_nominal_case(self):
        coeffs = np.full((8, 8), 2.0)
        quant_table = np.full((8, 8), 3.0)

        result = dequantize(coeffs, quant_table)

        assert np.all(result == 6.0)

    def test_edge_case_shape_mismatch(self):
        with pytest.raises(ValueError):
            dequantize(np.zeros((8, 8)), np.zeros((4, 4)))


class TestQuantize:

    def test_nominal_case(self):
        coeffs = np.full((8, 8), 13.0)
        quant_table = np.full((8, 8), 4.0)

        result = quantize(coeffs, quant_table)

        assert np.all(result == 3.0)  # round(13/4) = round(3.25) = 3

    def test_edge_case_shape_mismatch(self):
        with pytest.raises(ValueError):
            quantize(np.zeros((8, 8)), np.zeros((4, 4)))

    def test_interop_dequantize_is_approximate_inverse(self):
        rng = np.random.default_rng(3)
        coeffs = rng.uniform(-500, 500, size=(8, 8))
        quant_table = np.full((8, 8), 8.0)

        quantized = quantize(coeffs, quant_table)
        recovered = dequantize(quantized, quant_table)

        assert np.max(np.abs(recovered - coeffs)) <= 4.0  # tolerance = pas de quantification / 2


class TestScaleQuantizationTable:

    def test_nominal_case_quality_50_returns_base_table_unchanged(self):
        result = scale_quantization_table(50)

        assert np.array_equal(result, STANDARD_LUMINANCE_QUANT_TABLE)

    def test_nominal_case_higher_quality_gives_finer_quantization(self):
        low_quality = scale_quantization_table(10)
        high_quality = scale_quantization_table(90)

        assert np.mean(high_quality) < np.mean(low_quality)

    def test_edge_case_invalid_quality(self):
        with pytest.raises(ValueError):
            scale_quantization_table(0)
        with pytest.raises(ValueError):
            scale_quantization_table(101)

    def test_interop_with_quantize_dequantize(self):
        quant_table = scale_quantization_table(75)
        rng = np.random.default_rng(4)
        coeffs = rng.uniform(-200, 200, size=(8, 8))

        quantized = quantize(coeffs, quant_table)
        recovered = dequantize(quantized, quant_table)

        assert np.max(np.abs(recovered - coeffs)) <= np.max(quant_table)
