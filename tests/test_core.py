from __future__ import annotations

import tempfile
import unittest
import asyncio
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

    def test_auto_palette_uses_single_source_color(self):
        from handlers.input_handler import _auto_palette_pair

        color1, color2 = _auto_palette_pair(["#E00000"])
        self.assertEqual(color1, "#E00000")
        self.assertNotEqual(color2, "#0B5CAD")
        r, g, b = tuple(int(color2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        self.assertGreater(r, g)
        self.assertGreater(r, b)

    def test_palette_prefers_saturated_green(self):
        from utils.palette import _dominant_colors

        img = Image.new("RGBA", (64, 64), (0, 180, 0, 255))
        colors = _dominant_colors(img)
        self.assertTrue(colors)
        r, g, b = tuple(int(colors[0].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        self.assertGreater(g, r)
        self.assertGreater(g, b)

    def test_auto_palette_icon_is_premiumized(self):
        from utils.i18n import t

        rendered = t("ru", "preview_bg_auto_palette")
        self.assertIn("tg-emoji", rendered)

    def test_empty_auto_palette_does_not_replace_background_with_gray(self):
        from handlers.input_handler import _apply_auto_palette

        settings = self.state.reset(4242424245)
        settings["background"]["auto_palette"] = True
        settings["background"]["color"] = "#00AA00"
        settings["background"]["color2"] = "#006600"
        settings["input"]["type"] = "missing"
        _apply_auto_palette(4242424245, settings)
        self.assertEqual(settings["background"]["color"], "#00AA00")
        self.assertEqual(settings["background"]["color2"], "#006600")

    def test_auto_colorize_does_not_use_stale_image_background_color(self):
        settings = self.state.reset(4242424244)
        settings["input"]["type"] = "emoji"
        settings["input"]["emoji"] = "🔴"
        settings["input"]["colorize"]["enabled"] = True
        settings["input"]["colorize"]["auto"] = True
        settings["background"]["mode"] = "global_image"
        settings["background"]["color"] = "#0000FF"
        settings["output"]["format"] = "png"
        settings["output"]["width"] = 128
        settings["output"]["height"] = 128
        result = self.renderer.render(settings, None, None, None)
        with Image.open(result).convert("RGBA") as img:
            pixels = [
                (r, g, b)
                for r, g, b, a in img.getdata()
                if a > 0 and (r, g, b) != (0, 0, 0)
            ]
        avg = tuple(sum(p[i] for p in pixels) / len(pixels) for i in range(3))
        self.assertGreater(avg[0], avg[2])

    def test_render_queue_fifo_positions(self):
        async def scenario():
            from utils.render_queue import enqueue_render

            uid = 989898
            first = await enqueue_render(uid)
            second = await enqueue_render(uid)
            self.assertEqual(await first.position(), 1)
            self.assertEqual(await second.position(), 2)
            await first.release()
            self.assertEqual(await second.position(), 1)
            await second.release()

        asyncio.run(scenario())

    def test_render_snapshot_keeps_original_input_file(self):
        from handlers.render import _snapshot_render_job

        uid = 4242424246
        settings = self.state.reset(uid)
        settings["input"]["type"] = "sticker"
        from utils.files import user_dir as get_user_dir

        udir = get_user_dir(uid)
        udir.mkdir(parents=True, exist_ok=True)
        src = udir / "input.webp"
        src.write_bytes(b"first")
        snapshot, input_path, _bg, _wm, snapshot_dir = _snapshot_render_job(uid, settings)
        try:
            src.write_bytes(b"second")
            self.assertEqual(snapshot["input"]["type"], "sticker")
            self.assertIsNotNone(input_path)
            self.assertEqual(input_path.read_bytes(), b"first")
        finally:
            import shutil

            shutil.rmtree(snapshot_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
