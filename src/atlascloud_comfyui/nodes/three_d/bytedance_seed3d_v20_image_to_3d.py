from __future__ import annotations

from typing import Any, Dict, Tuple

from ..auth.atlas_client_node import AtlasClientHandle
from ._common import resolve_image, run_3d_job


class AtlasSeed3DV20ImageTo3D:
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
                        "tooltip": "Source image URL or base64/data-URL. <4096x4096 px, <=10 MB, aspect ratio 0.4-2.5, jpg/jpeg/png/webp/bmp",
                    },
                ),
            },
            "optional": {
                "subdivision_level": (
                    ["high", "medium", "low"],
                    {"default": "medium", "tooltip": "Mesh density: high=1,000,000 / medium=500,000 / low=100,000 faces"},
                ),
                "file_format": (
                    ["glb", "obj", "usd", "usdz"],
                    {"default": "glb", "tooltip": "Output format. Delivered as a .zip containing a single file"},
                ),
                "poll_interval_sec": ("FLOAT", {"default": 3.0, "min": 0.5, "max": 30.0, "tooltip": "Polling interval (seconds)"}),
                "timeout_sec": ("INT", {"default": 900, "min": 30, "max": 7200, "tooltip": "Timeout (seconds)"}),
            },
        }

    def run(
        self,
        atlas_client: AtlasClientHandle,
        image: str,
        subdivision_level: str = "medium",
        file_format: str = "glb",
        poll_interval_sec: float = 3.0,
        timeout_sec: int = 900,
    ) -> Tuple[str, str]:
        client = atlas_client.client

        payload: Dict[str, Any] = {
            "model": "bytedance/seed3d-v2.0/image-to-3d",
            "image": resolve_image(client, image),
            "subdivision_level": subdivision_level,
            "file_format": file_format,
        }

        return run_3d_job(
            client,
            payload,
            poll_interval_sec=poll_interval_sec,
            timeout_sec=timeout_sec,
        )
