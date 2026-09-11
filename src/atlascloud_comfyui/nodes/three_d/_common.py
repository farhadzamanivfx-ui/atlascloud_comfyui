"""Shared helpers for the AtlasCloud 3D generation nodes.

Import-safe: no comfy/folder_paths/requests at module import time.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


def extract_model_url(result: Dict[str, Any], prediction_id: str) -> str:
    """Pull the generated asset URL out of a completed prediction payload.

    The 3D models return the same envelope as the image models
    (``data.outputs``), but an entry can be a plain URL string or an object
    whose URL key varies (``url`` / ``model`` / ``file`` / ``output``).
    """
    outputs = (result.get("data") or {}).get("outputs") or []
    if not outputs:
        raise RuntimeError(f"No outputs returned for prediction {prediction_id}: {result}")

    first = outputs[0]
    if isinstance(first, dict):
        for key in ("url", "model", "model_url", "file", "file_url", "output"):
            value = first.get(key)
            if isinstance(value, str) and value.strip():
                return value
        raise RuntimeError(f"Unexpected output object for prediction {prediction_id}: {first}")

    if not isinstance(first, str):
        raise RuntimeError(
            f"Unexpected output type for prediction {prediction_id}: {type(first).__name__} {first!r}"
        )

    return first


def resolve_image(client: Any, image: str) -> str:
    """Normalize a node's image input into something the API accepts.

    Public URLs and ``asset://`` refs pass through; an inline data-URL / raw
    base64 image (e.g. from AtlasCloud Image-to-Base64) is uploaded first so the
    JSON body stays small and models that only accept URLs still work.
    """
    value = (image or "").strip()
    if not value:
        raise RuntimeError("image is required")
    resolved = client.resolve_reference_images([value])
    if not resolved:
        raise RuntimeError("image could not be resolved to a URL")
    return resolved[0]


def run_3d_job(
    client: Any,
    payload: Dict[str, Any],
    *,
    poll_interval_sec: float,
    timeout_sec: float,
) -> Tuple[str, str]:
    """Submit a 3D generation and wait for it; returns (model_url, prediction_id)."""
    prediction_id = client.generate_image(payload)
    result = client.poll_prediction(
        prediction_id,
        poll_interval_sec=float(poll_interval_sec),
        timeout_sec=float(timeout_sec),
    )
    return (extract_model_url(result, prediction_id), prediction_id)
