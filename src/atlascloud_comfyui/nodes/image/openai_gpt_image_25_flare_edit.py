from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..auth.atlas_client_node import AtlasClientHandle


class AtlasOpenAIGPTImage25FlareEdit:
    CATEGORY = "AtlasCloud/Image"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("image_url", "prediction_id", "image_urls")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "atlas_client": ("ATLAS_CLIENT",),
                "prompt": ("STRING", {"multiline": True, "tooltip": "Edit instruction (up to 32000 characters)"}),
                "images": (
                    "STRING",
                    {"multiline": True, "default": "", "tooltip": "1-16 source images, one per line: URL, base64/data-URL or asset://<ID>"},
                ),
            },
            "optional": {
                "mask": (
                    "STRING",
                    {"default": "", "tooltip": "Optional mask (URL, base64 or asset://). Transparent pixels = area to replace; must match the first image's size"},
                ),
                "size": (
                    ["auto", "1024x1024", "1024x768", "768x1024", "1024x1536", "1536x1024", "2048x2048", "2048x1152", "1152x2048", "2560x1088", "1088x2560", "2880x2160", "2160x2880", "3840x2160", "2160x3840"],
                    {"default": "1024x1024", "tooltip": "WIDTHxHEIGHT. Above 2560x1440 is experimental; max 3840x2160"},
                ),
                "quality": (
                    ["auto", "low", "medium", "high", "xhigh", "max"],
                    {"default": "medium", "tooltip": "Rendering tier. xhigh/max are new in 2.5 and cost more per image"},
                ),
                "background": (
                    ["auto", "opaque", "transparent"],
                    {"default": "auto", "tooltip": "transparent needs output_format png or webp"},
                ),
                "output_format": (["png", "jpeg", "webp"], {"default": "png", "tooltip": "Output image format"}),
                "moderation": (["auto", "low"], {"default": "auto", "tooltip": "low applies less restrictive filtering"}),
                "n": ("INT", {"default": 1, "min": 1, "max": 10, "tooltip": "Images to generate (each billed separately)"}),
                "poll_interval_sec": ("FLOAT", {"default": 2.0, "min": 0.5, "max": 10.0, "tooltip": "Polling interval (seconds)"}),
                "timeout_sec": ("INT", {"default": 600, "min": 30, "max": 7200, "tooltip": "Timeout (seconds)"}),
            },
        }

    def run(
        self,
        atlas_client: AtlasClientHandle,
        prompt: str,
        images: str,
        mask: str = "",
        size: str = "1024x1024",
        quality: str = "medium",
        background: str = "auto",
        output_format: str = "png",
        moderation: str = "auto",
        n: int = 1,
        poll_interval_sec: float = 2.0,
        timeout_sec: int = 600,
    ) -> Tuple[str, str, str]:
        p = (prompt or "").strip()
        if not p:
            raise RuntimeError("prompt is required")

        image_list: List[str] = [v.strip() for v in (images or "").splitlines() if v.strip()]
        if not image_list:
            raise RuntimeError("images is required (1-16 lines)")
        if len(image_list) > 16:
            raise RuntimeError("images maxItems is 16")

        # Inline base64 is uploaded first so up to 16 images don't blow the request size (HTTP 413).
        client = atlas_client.client

        payload: Dict[str, Any] = {
            "model": "openai/gpt-image-2.5-flare/edit",
            "prompt": p,
            "images": client.resolve_reference_images(image_list),
            "size": size,
            "quality": quality,
            "background": background,
            "output_format": output_format,
            "moderation": moderation,
            "n": int(n),
        }

        m = (mask or "").strip()
        if m:
            payload["mask"] = client.resolve_reference_images([m])[0]

        if background == "transparent" and output_format == "jpeg":
            raise RuntimeError("background=transparent needs output_format png or webp")

        prediction_id = client.generate_image(payload)
        result = client.poll_prediction(prediction_id, poll_interval_sec=float(poll_interval_sec), timeout_sec=float(timeout_sec))

        outputs = (result.get("data") or {}).get("outputs") or []
        urls: List[str] = []
        for item in outputs:
            if isinstance(item, dict):
                item = item.get("url") or item.get("image") or item.get("output")
            if isinstance(item, str) and item.strip():
                urls.append(item.strip())
        if not urls:
            raise RuntimeError(f"No outputs returned for prediction {prediction_id}: {result}")

        return (urls[0], prediction_id, "\n".join(urls))
