import numpy as np
import pytest
from matplotlib import image as mpimg

from satrx.image.io import save_image


class TestSaveImage:

    def test_nominal_case_roundtrip(self, tmp_path):
        image = np.zeros((4, 6, 3), dtype=np.uint8)
        image[0, 0] = [255, 0, 0]
        output_path = tmp_path / "meteor_pass" / "image.png"

        save_image(image, output_path)

        assert output_path.exists()
        reloaded = mpimg.imread(output_path)
        assert reloaded.shape[0] == 4
        assert reloaded.shape[1] == 6

    def test_edge_case_wrong_shape(self, tmp_path):
        grayscale = np.zeros((4, 6), dtype=np.uint8)

        with pytest.raises(ValueError):
            save_image(grayscale, tmp_path / "image.png")

    def test_edge_case_wrong_dtype(self, tmp_path):
        image = np.zeros((4, 6, 3), dtype=np.uint16)

        with pytest.raises(ValueError):
            save_image(image, tmp_path / "image.png")

    def test_interop_with_compose_rgb(self, tmp_path):
        from satrx.image.compose import compose_rgb

        red = np.full((5, 5), 200, dtype=np.uint16)
        green = np.full((5, 5), 100, dtype=np.uint16)
        blue = np.full((5, 5), 50, dtype=np.uint16)
        image = compose_rgb(red, green, blue, normalize=False)
        output_path = tmp_path / "composed.png"

        save_image(image, output_path)

        assert output_path.exists()
