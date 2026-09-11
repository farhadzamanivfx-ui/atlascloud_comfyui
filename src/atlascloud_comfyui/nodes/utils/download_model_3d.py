from __future__ import annotations

import os
import time
import uuid
import zipfile
import urllib.request
from urllib.parse import urlparse
from typing import Tuple

_MESH_EXTS = (".glb", ".gltf", ".obj", ".fbx", ".stl", ".usd", ".usdz", ".usda", ".usdc", ".ply", ".mp4")


def _guess_ext_from_url(url: str) -> str:
    path = urlparse(url).path or ""
    _, ext = os.path.splitext(path)
    ext = (ext or "").lower()
    if ext in _MESH_EXTS or ext == ".zip":
        return ext
    return ".glb"


def _download_file(url: str, dst_path: str, timeout_sec: int = 300) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "atlascloud-comfyui/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp, open(dst_path, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)  # 1MB
            if not chunk:
                break
            f.write(chunk)


def _extract_zip(zip_path: str, out_folder: str) -> str:
    """Unpack the archive next to it and return the mesh file inside it.

    Seed3D (and any model asked for OBJ/USD) delivers a .zip holding the mesh
    plus its side-car textures, which ComfyUI's 3D viewer cannot open directly.
    """
    stem = os.path.splitext(os.path.basename(zip_path))[0]
    dest = os.path.join(out_folder, stem)
    os.makedirs(dest, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if not m.endswith("/") and not m.startswith(("/", "..")) and ".." not in m]
        zf.extractall(dest, members=members)

    meshes = [m for m in members if os.path.splitext(m)[1].lower() in _MESH_EXTS]
    if not meshes:
        raise RuntimeError(f"No 3D mesh found inside {zip_path} (members: {members})")

    # Prefer glb/gltf when the archive carries several candidates.
    meshes.sort(key=lambda m: 0 if os.path.splitext(m)[1].lower() in (".glb", ".gltf") else 1)
    return os.path.join(dest, meshes[0].replace("/", os.sep))


class AtlasDownloadModel3D:
    """Save an AtlasCloud 3D result into ComfyUI's output folder.

    The 3D nodes hand back a remote URL. This node downloads it (unzipping the
    archive that some formats are delivered in) and returns both the absolute
    path and a ComfyUI annotated path such as ``atlascloud3d/foo.glb [output]``,
    which can be wired straight into ``Preview 3D`` / ``Load 3D``.
    """

    CATEGORY = "AtlasCloud/Utils"
    FUNCTION = "run"

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("model_file", "local_path")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_url": ("STRING", {"default": "", "tooltip": "Direct URL of the generated 3D file (glb/obj/fbx/usdz/zip)"}),
                "subfolder": ("STRING", {"default": "atlascloud3d", "tooltip": "Subfolder under ComfyUI output/"}),
            },
            "optional": {
                "filename_prefix": ("STRING", {"default": "Atlas3D", "tooltip": "Saved filename prefix"}),
                "timeout_sec": ("INT", {"default": 300, "min": 5, "max": 3600, "tooltip": "Download timeout (seconds)"}),
                "unzip": ("BOOLEAN", {"default": True, "tooltip": "Unpack .zip results and return the mesh inside"}),
            },
        }

    def run(
        self,
        model_url: str,
        subfolder: str,
        filename_prefix: str = "Atlas3D",
        timeout_sec: int = 300,
        unzip: bool = True,
    ) -> Tuple[str, str]:
        model_url = (model_url or "").strip()
        if not model_url.startswith("http://") and not model_url.startswith("https://"):
            raise RuntimeError("model_url must start with http:// or https://")

        try:
            import folder_paths  # type: ignore  # only at runtime

            output_dir = folder_paths.get_output_directory()
        except Exception:
            output_dir = os.path.expanduser("~/Documents/ComfyUI/output")

        safe_sub = (subfolder or "").strip().strip("/").strip("\\")
        out_folder = os.path.join(output_dir, safe_sub) if safe_sub else output_dir
        os.makedirs(out_folder, exist_ok=True)

        ext = _guess_ext_from_url(model_url)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        name = f"{filename_prefix}_{stamp}_{uuid.uuid4().hex[:8]}{ext}"
        dst_path = os.path.join(out_folder, name)

        _download_file(model_url, dst_path, timeout_sec=timeout_sec)

        if ext == ".zip" and unzip:
            dst_path = _extract_zip(dst_path, out_folder)

        # ComfyUI's 3D widgets take an annotated path relative to the output dir.
        rel = os.path.relpath(dst_path, output_dir).replace("\\", "/")
        return (f"{rel} [output]", dst_path)
