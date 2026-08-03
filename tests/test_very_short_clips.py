import unittest

from codecguard.core import demo, fixture, measure


class VeryShortClipsTest(unittest.TestCase):
    """The multi-resolution spectral-convergence loop floored frame_count
    to a minimum of 1 even when the clip was shorter than the FFT window
    size (512/2048/8192 samples). For any clip under 8192 samples (~170ms
    at 48kHz -- an ordinary length for a short SFX or dialogue snippet),
    the fancy-indexed reference[indices]/candidate[indices] reached past
    the signal's actual length and raised an uncaught IndexError."""

    def test_clips_under_8192_samples_do_not_crash(self):
        audio = fixture()
        for length in (8191, 5000, 2000, 500, 20):
            with self.subTest(length=length):
                clip = audio[:length]
                result = measure(clip, clip)
                self.assertTrue(result["passed"])

    def test_tiny_clip_still_measurable(self):
        audio = fixture()
        clip = audio[:20]
        result = measure(clip, clip)
        self.assertIn("spectral_convergence", result["metrics"])

    def test_demo_output_unaffected(self):
        result = demo()
        self.assertTrue(result["release_candidate"]["passed"])
        self.assertFalse(result["regression"]["passed"])


if __name__ == "__main__":
    unittest.main()
