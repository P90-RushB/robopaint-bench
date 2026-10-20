"""Start a private NVIDIA Xorg display in a disposable Colab GPU runtime.

Uses Colab's existing driver libraries; does not install or replace a driver.
The GLX check proves this display uses NVIDIA. Check the Unity Player log too.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


SOFTWARE_VARIABLES = (
    "LIBGL_ALWAYS_SOFTWARE", "GALLIUM_DRIVER", "GALLIUM_NUM_THREADS",
    "LP_NUM_THREADS", "MESA_LOADER_DRIVER_OVERRIDE", "LIBGL_DRIVERS_PATH",
)


def xorg_bus_id(value: str) -> str:
    match = re.fullmatch(r"([0-9a-fA-F]{4,8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])", value.strip())
    if not match:
        raise ValueError("Invalid GPU PCI bus identifier from nvidia-smi.")
    domain, bus, device, function = (int(part, 16) for part in match.groups())
    bus_part = f"{bus}@{domain}" if domain else str(bus)
    return f"PCI:{bus_part}:{device}:{function}"


def is_nvidia_glx(text: str) -> bool:
    return ("OpenGL vendor string: NVIDIA Corporation" in text
            and "OpenGL renderer string:" in text
            and not any(name in text.lower() for name in ("llvmpipe", "softpipe", "swrast")))


def start_display(output: Path, gpu_index: int = 0) -> dict:
    if os.name != "posix" or not shutil.which("Xorg"):
        raise RuntimeError("This helper needs Linux and xserver-xorg-core. Select a Colab GPU runtime.")
    nvidia = Path("/usr/lib64-nvidia")
    modules = nvidia / "xorg/modules"
    required = (nvidia / "libGLX_nvidia.so.0", modules / "drivers/nvidia_drv.so")
    if not all(path.is_file() for path in required):
        raise RuntimeError("Colab NVIDIA graphics libraries are missing. No CPU fallback was selected.")
    hardware = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=pci.bus_id,name,driver_version", "--format=csv,noheader"], text=True
    ).strip().splitlines()
    if not 0 <= gpu_index < len(hardware):
        raise ValueError("Requested GPU index is unavailable.")
    bus, name, driver = [part.strip() for part in hardware[gpu_index].split(",", 2)]
    bus_id = xorg_bus_id(bus)
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    number = next((n for n in range(99, 150)
                   if not Path(f"/tmp/.X11-unix/X{n}").exists()
                   and not Path(f"/tmp/.X{n}-lock").exists()), None)
    if number is None:
        raise RuntimeError("No free display number found; existing displays were left untouched.")
    display = f":{number}"
    conf = output / "xorg.conf"
    conf.write_text(f'''Section "Files"
    ModulePath "{modules}"
    ModulePath "/usr/lib/xorg/modules"
EndSection
Section "ServerFlags"
    Option "AutoAddDevices" "false"
    Option "AutoAddGPU" "false"
EndSection
Section "Device"
    Identifier "RoboPaintGPU"
    Driver "nvidia"
    BusID "{bus_id}"
    Option "AllowEmptyInitialConfiguration" "true"
EndSection
Section "Screen"
    Identifier "RoboPaintScreen"
    Device "RoboPaintGPU"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Virtual 1280 720
    EndSubSection
EndSection
''', encoding="utf-8")
    env = os.environ.copy()
    for key in SOFTWARE_VARIABLES:
        env.pop(key, None)
    env.update(DISPLAY=display, __GLX_VENDOR_LIBRARY_NAME="nvidia",
               LD_LIBRARY_PATH=str(nvidia) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""))
    stdout = (output / "xorg-stdout.log").open("w")
    try:
        process = subprocess.Popen(
            ["Xorg", display, "-config", str(conf), "-noreset", "-nolisten", "tcp",
             "-logfile", str(output / "Xorg.log")],
            env=env, stdout=stdout, stderr=subprocess.STDOUT, start_new_session=True,
        )
    finally:
        stdout.close()
    try:
        deadline = time.monotonic() + 30
        glx = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Xorg exited ({process.returncode}); inspect {output / 'Xorg.log'}.")
            glx = subprocess.run(["glxinfo", "-B"], env=env, capture_output=True, text=True, timeout=10)
            if glx.returncode == 0:
                break
            time.sleep(0.25)
        text = (glx.stdout + glx.stderr) if glx else "GLX check did not run."
        (output / "glxinfo.txt").write_text(text, encoding="utf-8")
        if glx is None or glx.returncode != 0 or not is_nvidia_glx(text):
            raise RuntimeError("NVIDIA GLX verification failed. Inspect glxinfo.txt; no software fallback was selected.")
        result = {
            "schema": "robopaint.colab-graphics.v1", "display": display,
            "xorg_pid": process.pid, "gpu": name, "driver": driver, "pci_bus_id": bus,
            "glx_nvidia_verified": True, "unity_renderer_verified": False,
            "environment": {key: env[key] for key in ("DISPLAY", "LD_LIBRARY_PATH", "__GLX_VENDOR_LIBRARY_NAME")},
            "unset_environment": list(SOFTWARE_VARIABLES),
            "note": "GLX verification is not proof of the Unity renderer. Inspect its Player log and observations.",
        }
        (output / "graphics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    except BaseException:
        # Only the exact process created above is ours to stop.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for display receipts/logs")
    parser.add_argument("--gpu-index", type=int, default=0)
    args = parser.parse_args()
    result = start_display(args.output_dir, args.gpu_index)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
