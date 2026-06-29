from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import os

from PIL import Image


class CoreChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["DB_PATH"] = str(Path(cls.tmp.name) / "test.sqlite3")
        from services import renderer
        from utils import health, state

        cls.renderer = renderer
        cls.health = health
        cls.state = state

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_state_roundtrip(self):
        uid = 4242424242
        settings = self.state.reset(uid)
        settings["lang"] = "en"
        self.state.save(uid)
        self.assertEqual(self.state.get(uid)["lang"], "en")
        self.state.set_await(uid, "wm_text")
        self.assertEqual(self.state.get_await(uid), "wm_text")
        self.state.set_await(uid, None)
        self.assertIsNone(self.state.get_await(uid))

    def test_health_report_shape(self):
        report = self.health.health_report()
        self.assertIn("sqlite", report)
        self.assertIn("tmp_size", report)

    def test_emoji_png_render(self):
        settings = self.state.reset(4242424243)
        settings["input"]["type"] = "emoji"
        settings["input"]["emoji"] = "✨"
        settings["output"]["format"] = "png"
        settings["output"]["width"] = 128
        settings["output"]["height"] = 128
        result = self.renderer.render(settings, None, None, None)
        self.assertTrue(result.exists())
        with Image.open(result) as img:
            self.assertEqual(img.size, (128, 128))


if __name__ == "__main__":
    unittest.main()
