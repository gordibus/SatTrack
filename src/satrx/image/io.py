from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib import image as mpimg
from numpy.typing import NDArray


def save_image(image: NDArray[np.uint8], path: Path) -> None:
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"image doit etre de forme (H, W, 3), recu {image.shape}")
    if image.dtype != np.uint8:
        raise ValueError(f"image doit etre en uint8, recu dtype={image.dtype}")

    path.parent.mkdir(parents=True, exist_ok=True)
    mpimg.imsave(path, image)
