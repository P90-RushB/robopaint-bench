"""Check interpretation of external GPU/GLX identities without starting a display."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/colab_graphics.py"
SPEC = importlib.util.spec_from_file_location("colab_graphics", PATH)
graphics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(graphics)


class GraphicsIdentityTests(unittest.TestCase):
    def test_pci_bus_conversion_uses_decimal_and_preserves_domain(self):
        self.assertEqual("PCI:0:4:0", graphics.xorg_bus_id("00000000:00:04.0"))
        self.assertEqual("PCI:101@1:26:1", graphics.xorg_bus_id("0001:65:1a.1"))
        for value in ("", "0:4:0", "0000:00:04.9", '0000:00:04.0"\nEndSection'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                graphics.xorg_bus_id(value)

    def test_cuda_allocation_is_not_a_glx_renderer_receipt(self):
        self.assertFalse(graphics.is_nvidia_glx("NVIDIA-SMI Tesla T4"))
        self.assertFalse(graphics.is_nvidia_glx("OpenGL vendor string: Mesa\nOpenGL renderer string: llvmpipe"))
        self.assertFalse(graphics.is_nvidia_glx("OpenGL vendor string: NVIDIA Corporation\nOpenGL renderer string: llvmpipe"))
        self.assertTrue(graphics.is_nvidia_glx("OpenGL vendor string: NVIDIA Corporation\nOpenGL renderer string: Tesla T4/PCIe/SSE2"))


if __name__ == "__main__":
    unittest.main()
