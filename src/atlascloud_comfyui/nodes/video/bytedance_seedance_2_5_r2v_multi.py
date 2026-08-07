from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..auth.atlas_client_node import AtlasClientHandle

MAX_IMAGES = 30
MAX_VIDEOS = 10


class AtlasSeedance25ReferenceToVideoMulti:
    """Seedance 2.5 Reference-to-Video with up to 30 image + 10 video reference slots.

    Each slot is a separate socket (URL or base64 string). Empty slots are ignored.
    Total references are capped by the model at 50 multimodal references.
    """

    CATEGORY = "AtlasCloud/Video"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("video_url", "prediction_id")

    @classmethod
    def INPUT_TYPES(cls):
        optional: Dict[str, Any] = {
            "prompt": (
                "STRING",
                {
                    "multiline": True,
                    "default": "The character in image 1 dances gracefully to the music",
                    "tooltip": "Prompt (optional). Supports timeline prompting: describe what happens at each second.",
                },
            ),
            "reference_audios": (
                "STRING",
                {"multiline": True, "default": "", "tooltip": "Reference audio URLs, one per line (up to 3, each wav/mp3 2-15s ≤15MB)"},
            ),
            "duration": (
                ["-1", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "20", "25", "30"],
                {"default": "5", "tooltip": "Duration (seconds), or -1 for auto. Seedance 2.5 supports up to 30s native, single continuous shot."},
            ),
            "resolution": (["480p", "720p", "720p-SR", "1080p", "1080p-SR", "1440p-SR", "4k"], {"default": "720p", "tooltip": "Resolution. Atlas Cloud currently supports 720p; higher tiers roll out via the ByteDance API."}),
            "bitrate_mode": (["standard", "high"], {"default": "standard", "tooltip": "Output bitrate. 'high' = crisper, larger file. Does not affect token cost."}),
            "ratio": (
                ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"],
                {"default": "adaptive", "tooltip": "Aspect ratio (adaptive = auto)"},
            ),
            "randomize_seed": ("BOOLEAN", {"default": True, "tooltip": "开启后每次生成随机结果；关闭后使用下方固定 seed"}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 4294967295, "tooltip": "固定 seed（仅在随机开关关闭时生效）"}),
            "generate_audio": ("BOOLEAN", {"default": True, "tooltip": "Generate audio (native ambience/foley in same pass)"}),
            "watermark": ("BOOLEAN", {"default": False, "tooltip": "Add watermark"}),
            "return_last_frame": ("BOOLEAN", {"default": False, "tooltip": "Return last frame (if supported)"}),
            "poll_interval_sec": (
                "FLOAT",
                {"default": 2.0, "min": 0.5, "max": 10.0, "tooltip": "Polling interval (seconds)"},
            ),
            "timeout_sec": (
                "INT",
                {"default": 900, "min": 30, "max": 7200, "tooltip": "Timeout (seconds)"},
            ),
        }

        # 30 image reference sockets
        for i in range(1, MAX_IMAGES + 1):
            optional[f"image_{i}"] = (
                "STRING",
                {"default": "", "forceInput": True, "tooltip": f"Reference image {i} (URL or base64)"},
            )
        # 10 video reference sockets
        for i in range(1, MAX_VIDEOS + 1):
            optional[f"video_{i}"] = (
                "STRING",
                {"default": "", "forceInput": True, "tooltip": f"Reference video {i} (URL)"},
            )

        return {
            "required": {
                "atlas_client": ("ATLAS_CLIENT",),
            },
            "optional": optional,
        }

    def run(
        self,
        atlas_client: AtlasClientHandle,
        prompt: str = "The character in image 1 dances gracefully to the music",
        reference_audios: str = "",
        randomize_seed: bool = True,
        seed: int = 0,
        duration: int = 5,
        resolution: str = "720p",
        ratio: str = "adaptive",
        bitrate_mode: str = "standard",
        generate_audio: bool = True,
        watermark: bool = False,
        return_last_frame: bool = False,
        poll_interval_sec: float = 2.0,
        timeout_sec: int = 900,
        **kwargs: Any,
    ) -> Tuple[str, str]:
        # Collect image/video slots in order, skipping empties
        ref_imgs: List[str] = []
        for i in range(1, MAX_IMAGES + 1):
            v = (kwargs.get(f"image_{i}") or "").strip()
            if v:
                ref_imgs.append(v)

        ref_vids: List[str] = []
        for i in range(1, MAX_VIDEOS + 1):
            v = (kwargs.get(f"video_{i}") or "").strip()
            if v:
                ref_vids.append(v)

        if not ref_imgs and not ref_vids:
            raise RuntimeError("Provide at least one reference image or reference video")

        total_refs = len(ref_imgs) + len(ref_vids)
        if total_refs > 50:
            raise RuntimeError(
                f"Too many references: {total_refs} (model supports up to 50 multimodal references)"
            )

        client = atlas_client.client

        payload: Dict[str, Any] = {
            "model": "bytedance/seedance-2.5/reference-to-video",
            "duration": int(duration),
            "resolution": resolution,
            "ratio": ratio,
            "bitrate_mode": bitrate_mode,
            "generate_audio": bool(generate_audio),
            "watermark": bool(watermark),
            "return_last_frame": bool(return_last_frame),
        }

        if not randomize_seed:
            payload["seed"] = seed

        p = (prompt or "").strip()
        if p:
            payload["prompt"] = p

        ref_auds: List[str] = [v.strip() for v in (reference_audios or "").splitlines() if v.strip()]
        if ref_auds:
            payload["reference_audios"] = ref_auds

        if ref_imgs:
            payload["reference_images"] = ref_imgs
        if ref_vids:
            payload["reference_videos"] = ref_vids

        prediction_id = client.generate_video(payload)
        result = client.poll_prediction(
            prediction_id,
            poll_interval_sec=float(poll_interval_sec),
            timeout_sec=float(timeout_sec),
        )

        outputs = (result.get("data") or {}).get("outputs") or []
        if not outputs:
            raise RuntimeError(f"No outputs returned for prediction {prediction_id}: {result}")

        first = outputs[0]
        if not isinstance(first, str):
            raise RuntimeError(
                f"Unexpected output type for prediction {prediction_id}: {type(first).__name__} {first!r}"
            )

        return (first, prediction_id)
