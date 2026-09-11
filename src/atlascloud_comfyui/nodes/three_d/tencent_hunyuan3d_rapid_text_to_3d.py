from __future__ import annotations

from typing import Any, Dict, Tuple

from ..auth.atlas_client_node import AtlasClientHandle
from ._common import run_3d_job


class AtlasHunyuan3DRapidTextTo3D:
    CATEGORY = "AtlasCloud/3D"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("model_url", "prediction_id")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "atlas_client": ("ATLAS_CLIENT",),
                "prompt": (
                    "STRING",
                    {"multiline": True, "tooltip": "Description of the 3D content to generate (up to 1024 characters)"},
                ),
            },
            "optional": {
                "format": (
                    ["GLB", "OBJ", "USDZ", "FBX", "STL", "MP4"],
                    {"default": "GLB", "tooltip": "Output 3D file format"},
                ),
                "enable_pbr": ("BOOLEAN", {"default": False, "tooltip": "Generate PBR maps (metallic, roughness, normal)"}),
                "enable_geometry": ("BOOLEAN", {"default": False, "tooltip": "Also output an untextured geometry-only mesh (delivered as GLB)"}),
                "poll_interval_sec": ("FLOAT", {"default": 3.0, "min": 0.5, "max": 30.0, "tooltip": "Polling interval (seconds)"}),
                "timeout_sec": ("INT", {"default": 900, "min": 30, "max": 7200, "tooltip": "Timeout (seconds)"}),
            },
        }

    def run(
        self,
        atlas_client: AtlasClientHandle,
        prompt: str,
        format: str = "GLB",
        enable_pbr: bool = False,
        enable_geometry: bool = False,
        poll_interval_sec: float = 3.0,
        timeout_sec: int = 900,
    ) -> Tuple[str, str]:
        p = (prompt or "").strip()
        if not p:
            raise RuntimeError("prompt is required")

        client = atlas_client.client

        payload: Dict[str, Any] = {
            "model": "tencent/hunyuan3d-rapid/text-to-3d",
            "prompt": p,
            "format": format,
            "enable_pbr": bool(enable_pbr),
            "enable_geometry": bool(enable_geometry),
        }

        return run_3d_job(
            client,
            payload,
            poll_interval_sec=poll_interval_sec,
            timeout_sec=timeout_sec,
        )
