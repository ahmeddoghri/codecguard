"""Run the gate against codecs people actually ship, at real bitrates."""
import shutil
import unittest
from tempfile import TemporaryDirectory

from codecguard.core import CONTAINER_FOR_CODEC, benchmark, container_for

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _encoders() -> set[str]:
    import subprocess
    out = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-encoders"],
                         capture_output=True, text=True).stdout
    return {line.split()[1] for line in out.splitlines() if line.startswith(" A")}


@unittest.skipUnless(HAS_FFMPEG, "needs ffmpeg")
class RealCodecTest(unittest.TestCase):
    def test_container_is_chosen_from_a_table_not_the_codec_name(self):
        # "candidate.libopus" is not a container ffmpeg can mux.
        self.assertEqual(container_for("libopus"), "opus")
        self.assertEqual(container_for("libmp3lame"), "mp3")
        self.assertEqual(container_for("aac"), "m4a")
        with self.assertRaises(ValueError):
            container_for("not_a_codec")

    def test_lossless_flac_is_a_perfect_round_trip(self):
        if "flac" not in _encoders():
            self.skipTest("flac encoder unavailable")
        with TemporaryDirectory() as directory:
            result = benchmark(directory, codec="flac", bitrate="192k")
        self.assertTrue(result["passed"])
        self.assertGreater(result["metrics"]["snr_db"], 90)
        self.assertEqual(result["metrics"]["spectral_convergence"], 0.0)

    def test_a_healthy_bitrate_passes_and_a_starved_one_fails(self):
        available = _encoders()
        for codec, good, bad in (("aac", "192k", "64k"), ("libopus", "96k", "24k"), ("libmp3lame", "128k", "32k")):
            if codec not in available:
                continue
            with self.subTest(codec=codec):
                with TemporaryDirectory() as directory:
                    healthy = benchmark(directory, codec=codec, bitrate=good)
                with TemporaryDirectory() as directory:
                    starved = benchmark(directory, codec=codec, bitrate=bad)
                self.assertTrue(healthy["passed"], healthy["metrics"])
                self.assertFalse(starved["passed"], starved["metrics"])
                self.assertGreater(healthy["metrics"]["snr_db"], starved["metrics"]["snr_db"])

    def test_every_codec_in_the_table_names_a_plain_extension(self):
        for codec, extension in CONTAINER_FOR_CODEC.items():
            self.assertTrue(extension.isalnum(), (codec, extension))


if __name__ == "__main__":
    unittest.main()
