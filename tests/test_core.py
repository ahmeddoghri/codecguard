import shutil, tempfile, unittest
from codecguard.core import benchmark, demo, fixture, measure

class CodecGuardTests(unittest.TestCase):
    def test_identity_passes(self):
        audio=fixture(); self.assertTrue(measure(audio,audio)["passed"])
    def test_demo_catches_regression(self):
        result=demo(); self.assertTrue(result["release_candidate"]["passed"]); self.assertFalse(result["regression"]["passed"])
    @unittest.skipUnless(shutil.which("ffmpeg"),"ffmpeg required")
    def test_real_aac_round_trip(self):
        with tempfile.TemporaryDirectory() as directory: result=benchmark(directory)
        self.assertTrue(result["passed"],result)
    def test_short_inputs_remain_measurable(self):
        audio=fixture()[:10000]; self.assertIn("spectral_convergence",measure(audio,audio)["metrics"])

if __name__=="__main__": unittest.main()
