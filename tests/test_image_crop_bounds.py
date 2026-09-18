"""Regression coverage for floating-point crop boxes after browser resizing."""

import unittest

from PIL import Image

from image_utils import _fit_background_fixed


class ImageCropBoundsTests(unittest.TestCase):
    def test_browser_resized_landscape_renders_square(self):
        # The browser caps a 1536x864 upload at 1500x844. The old division
        # yielded source_h=844.0000000000001 and a negative top offset.
        image = Image.new("RGB", (1500, 844), "orange")
        poster = _fit_background_fixed(image, (1080, 1080))
        self.assertEqual(poster.size, (1080, 1080))
        self.assertEqual(poster.getpixel((0, 0)), (255, 165, 0))

    def test_crop_edges_stay_inside_landscape_and_portrait_sources(self):
        for source in ((1500, 844), (844, 1500), (1536, 864), (1, 73), (73, 1)):
            image = Image.new("RGB", source, "navy")
            for target in ((1080, 1080), (1080, 1350)):
                for position in ((0, 0), (0.5, 0.5), (1, 1), (0.1, 0.9)):
                    with self.subTest(source=source, target=target, position=position):
                        poster = _fit_background_fixed(image, target, position)
                        self.assertEqual(poster.size, target)
                        self.assertEqual(poster.getpixel((0, 0)), (0, 0, 128))
                        self.assertEqual(poster.getpixel((target[0] - 1, target[1] - 1)), (0, 0, 128))

    def test_crop_position_still_selects_requested_side(self):
        image = Image.new("RGB", (1500, 844), "red")
        image.paste("blue", (750, 0, 1500, 844))
        left = _fit_background_fixed(image, (1080, 1080), (0, 0.5))
        right = _fit_background_fixed(image, (1080, 1080), (1, 0.5))
        self.assertEqual(left.getpixel((540, 540)), (255, 0, 0))
        self.assertEqual(right.getpixel((540, 540)), (0, 0, 255))


if __name__ == "__main__":
    unittest.main()
