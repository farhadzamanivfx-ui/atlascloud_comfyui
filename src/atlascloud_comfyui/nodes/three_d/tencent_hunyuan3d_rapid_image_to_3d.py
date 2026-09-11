from __future__ import annotations

from typing import Any, Dict, Tuple

from ..auth.atlas_client_node import AtlasClientHandle
from ._common import resolve_image, run_3d_job


class AtlasHunyuan3DRapidImageTo3D:
    CATEGORY = "AtlasCloud/3D"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("model_url", "prediction_id")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "atlas_client": ("ATLAS_CLIENT",),
                "image": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Source image URL or base64/data-URL. 128-5000 px per side, <=4.5 MB, jpg/jpeg/png/webp. Best with a plain background and one object filling >50% of the frame",
                    },
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
        image: str,
        format: str = "GLB",
        enable_pbr: bool = False,
        enable_geometry: bool = False,
        poll_interval_sec: float = 3.0,
        timeout_sec: int = 900,
    ) -> Tuple[str, str]:
        client = atlas_client.client

        payload: Dict[str, Any] = {
            "model": "tencent/hunyuan3d-rapid/image-to-3d",
            "image": resolve_image(client, image),
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
