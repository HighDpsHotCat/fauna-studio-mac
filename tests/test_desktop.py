"""Exercise platform integration without downloading AI model weights."""

import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication

from app import Studio
from glb_info import triangle_count
from lowpoly_dialog import blender_executable, find_blender
from mesh_panel import MeshPanel
from web_viewer import LocalViewer


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "red-fox-lowpoly-3000.glb"


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, condition):
        deadline = time.monotonic() + 20
        while not condition():
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("The worker did not finish in time.")
            time.sleep(0.02)

    def test_inference_dependencies_import(self):
        import torch
        import open_clip
        import rembg
        import onnxruntime
        import mesh_worker
        from tsr.system import TSR

        self.assertIn("CPUExecutionProvider", onnxruntime.get_available_providers())
        self.assertTrue(callable(TSR))
        self.assertTrue(callable(rembg.remove))
        self.assertTrue(callable(open_clip.create_model_from_pretrained))
        self.assertTrue(callable(mesh_worker.reconstruct))
        self.assertEqual(torch.ones(1).item(), 1)

    def test_studio_and_viewer(self):
        studio = Studio()
        viewer = LocalViewer()
        try:
            self.assertIn("Fauna Studio", studio.windowTitle())
            url = viewer.url_for(EXAMPLE)
            parsed = urlsplit(url)
            base = parsed.scheme + "://" + parsed.netloc
            token = parse_qs(parsed.query)["model"][0]
            with urlopen(url, timeout=5) as response:
                self.assertIn(b"viewer.js", response.read())
            with urlopen(base + "/vendor/three/build/three.module.js", timeout=5) as response:
                self.assertGreater(len(response.read()), 10_000)
            with urlopen(base + "/models/" + token, timeout=5) as response:
                self.assertEqual(response.read(), EXAMPLE.read_bytes())
            self.assertEqual(triangle_count(EXAMPLE), 3000)
        finally:
            viewer.close()
            studio.close()

    def test_mac_blender_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            bundle = home / "Applications" / "Blender.app"
            binary = bundle / "Contents" / "MacOS" / "Blender"
            binary.parent.mkdir(parents=True)
            binary.touch()
            self.assertEqual(blender_executable(bundle), binary)
            self.assertEqual(blender_executable(binary), binary)
            self.assertIsNone(blender_executable(home / "missing.app"))
            with patch("lowpoly_dialog.sys.platform", "darwin"), \
                 patch("lowpoly_dialog.Path.glob", return_value=[bundle]), \
                 patch("lowpoly_dialog.shutil.which", return_value=None), \
                 patch("lowpoly_dialog.QSettings") as settings:
                settings.return_value.value.return_value = ""
                self.assertEqual(find_blender(), binary)

    def run_mesh_worker(self, cancel):
        with tempfile.TemporaryDirectory(prefix="fauna 맥 테스트 ") as folder:
            directory = Path(folder)
            worker = directory / "worker.py"
            worker.write_text(
                "import json, shutil, sys, time\n"
                "from pathlib import Path\n"
                "from PIL import Image\n"
                "work = Path(sys.argv[1])\n"
                "source = json.loads((work / 'source.json').read_text(encoding='utf-8'))\n"
                "assert Path(sys.prefix) == Path(source['prefix'])\n"
                "assert Image.open(work / 'input.png').size == (8, 8)\n"
                "print('ready', flush=True)\n"
                "time.sleep(60 if source['cancel'] else 0)\n"
                "shutil.copyfile(source['example'], work / 'mesh.glb')\n",
                encoding="utf-8",
            )
            output = directory / "붉은 여우.glb"
            output.write_bytes(b"existing file")
            panel = MeshPanel()
            panel.choose_output = lambda _: output
            try:
                with patch("mesh_panel.WORKER", worker):
                    panel.start(dict(title="테스트 사진", prefix=sys.prefix,
                                     example=str(EXAMPLE), cancel=cancel),
                                Image.new("RGB", (8, 8)))
                self.assertTrue(panel.busy)
                if cancel:
                    self.wait_until(lambda: panel.stage == "ready" or not panel.busy)
                    self.assertTrue(panel.busy, panel.note.text())
                    panel.cancel()
                self.wait_until(lambda: not panel.busy)
                self.assertEqual(output.read_bytes(), b"existing file" if cancel else EXAMPLE.read_bytes())
                self.assertFalse(list(directory.glob(".fauna-*")))
            finally:
                panel.shutdown()
                panel.close()

    def test_mesh_worker_in_current_environment(self):
        self.run_mesh_worker(cancel=False)

    def test_mesh_cancellation_preserves_existing_file(self):
        self.run_mesh_worker(cancel=True)


if __name__ == "__main__":
    unittest.main()
