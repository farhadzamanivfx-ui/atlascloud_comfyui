from __future__ import annotations

from typing import Any, Dict, Tuple

from ..auth.atlas_client_node import AtlasClientHandle
from ._common import resolve_image, run_3d_job


class AtlasTripoH31ImageTo3D:
    CATEGORY = "AtlasCloud/3D"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("model_url", "prediction_id")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "atlas_client": ("ATLAS_CLIENT",),
                "image_url": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Input image. A public URL, or base64/data-URL which is uploaded first (this model reads the image by URL)",
                    },
                ),
            },
            "optional": {
                "texture": ("BOOLEAN", {"default": True, "tooltip": "Enable texture generation"}),
                "pbr": ("BOOLEAN", {"default": True, "tooltip": "Generate PBR materials"}),
                "texture_quality": (["standard", "detailed"], {"default": "standard", "tooltip": "Texture resolution level"}),
                "geometry_quality": (["standard", "detailed"], {"default": "standard", "tooltip": "Geometry quality level"}),
                "texture_alignment": (
                    ["original_image", "geometry"],
                    {"default": "original_image", "tooltip": "How the texture is aligned to the mesh"},
                ),
                "orientation": (["default", "align_image"], {"default": "default", "tooltip": "Model orientation strategy"}),
                "face_limit": (
                    "INT",
                    {"default": 0, "min": 0, "max": 2000000, "tooltip": "Target face count (1000-2000000). 0 = adaptive"},
                ),
                "auto_size": ("BOOLEAN", {"default": False, "tooltip": "Auto-scale the model to real-world dimensions (meters)"}),
                "quad": ("BOOLEAN", {"default": False, "tooltip": "Quad mesh topology. Outputs FBX when enabled"}),
                "model_seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1, "tooltip": "Geometry seed. -1 = random"}),
                "texture_seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1, "tooltip": "Texture seed. -1 = random"}),
                "poll_interval_sec": ("FLOAT", {"default": 3.0, "min": 0.5, "max": 30.0, "tooltip": "Polling interval (seconds)"}),
                "timeout_sec": ("INT", {"default": 1800, "min": 30, "max": 7200, "tooltip": "Timeout (seconds)"}),
            },
        }

    def run(
        self,
        atlas_client: AtlasClientHandle,
        image_url: str,
        texture: bool = True,
        pbr: bool = True,
        texture_quality: str = "standard",
        geometry_quality: str = "standard",
        texture_alignment: str = "original_image",
        orientation: str = "default",
        face_limit: int = 0,
        auto_size: bool = False,
        quad: bool = False,
        model_seed: int = -1,
        texture_seed: int = -1,
        poll_interval_sec: float = 3.0,
        timeout_sec: int = 1800,
    ) -> Tuple[str, str]:
        client = atlas_client.client

        payload: Dict[str, Any] = {
            "model": "tripo-h3.1/image-to-3d",
            "image_url": resolve_image(client, image_url),
            "texture": bool(texture),
            "pbr": bool(pbr),
            "texture_quality": texture_quality,
            "geometry_quality": geometry_quality,
            "texture_alignment": texture_alignment,
            "orientation": orientation,
            "auto_size": bool(auto_size),
            "quad": bool(quad),
        }

        if int(face_limit) > 0:
            if not 1000 <= int(face_limit) <= 2000000:
                raise RuntimeError("face_limit must be 0 (adaptive) or between 1000 and 2000000")
            payload["face_limit"] = int(face_limit)

        for key, value in (("model_seed", model_seed), ("texture_seed", texture_seed)):
            if int(value) >= 0:
                payload[key] = int(value)

        return run_3d_job(
            client,
            payload,
            poll_interval_sec=poll_interval_sec,
            timeout_sec=timeout_sec,
        )
