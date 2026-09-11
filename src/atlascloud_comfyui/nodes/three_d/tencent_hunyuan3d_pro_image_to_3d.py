from __future__ import annotations

from typing import Any, Dict, Tuple

from ..auth.atlas_client_node import AtlasClientHandle
from ._common import resolve_image, run_3d_job


class AtlasHunyuan3DProImageTo3D:
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
                        "tooltip": "Source image URL or base64/data-URL. 128-5000 px per side, <=6 MB, jpg/jpeg/png/webp. Best with a plain background and one object filling >50% of the frame",
                    },
                ),
            },
            "optional": {
                "generate_type": (
                    ["Normal", "Geometry"],
                    {"default": "Normal", "tooltip": "Normal = textured mesh, Geometry = untextured white model (ignores enable_pbr)"},
                ),
                "enable_pbr": ("BOOLEAN", {"default": False, "tooltip": "Generate PBR maps (metallic, roughness, normal). No effect when generate_type is Geometry"}),
                "face_count": (
                    "INT",
                    {"default": 0, "min": 0, "max": 1500000, "tooltip": "Polygon faces (40000-1500000). 0 = leave to the model (500000)"},
                ),
                "poll_interval_sec": ("FLOAT", {"default": 3.0, "min": 0.5, "max": 30.0, "tooltip": "Polling interval (seconds)"}),
                "timeout_sec": ("INT", {"default": 1800, "min": 30, "max": 7200, "tooltip": "Timeout (seconds)"}),
            },
        }

    def run(
        self,
        atlas_client: AtlasClientHandle,
        image: str,
        generate_type: str = "Normal",
        enable_pbr: bool = False,
        face_count: int = 0,
        poll_interval_sec: float = 3.0,
        timeout_sec: int = 1800,
    ) -> Tuple[str, str]:
        client = atlas_client.client

        payload: Dict[str, Any] = {
            "model": "tencent/hunyuan3d-pro/image-to-3d",
            "image": resolve_image(client, image),
            "generate_type": generate_type,
            "enable_pbr": bool(enable_pbr),
        }

        if int(face_count) > 0:
            if not 40000 <= int(face_count) <= 1500000:
                raise RuntimeError("face_count must be 0 (auto) or between 40000 and 1500000")
            payload["face_count"] = int(face_count)

        return run_3d_job(
            client,
            payload,
            poll_interval_sec=poll_interval_sec,
            timeout_sec=timeout_sec,
        )
