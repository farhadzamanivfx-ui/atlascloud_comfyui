"""Metadata-only tests for the GPT Image 2.5 nodes (community edition, 2026-09-11).

New models: GPT Image 2.5 Sunburst and Flare (text-to-image + edit).
These tests MUST NOT require ATLASCLOUD_API_KEY.
"""

import importlib
import inspect

import pytest

GPT25_NODES = [
    ("AtlasCloud GPT Image-2.5 Sunburst Text-to-Image", "openai_gpt_image_25_sunburst_t2i", "AtlasOpenAIGPTImage25SunburstTextToImage", "openai/gpt-image-2.5-sunburst/text-to-image", False),
    ("AtlasCloud GPT Image-2.5 Sunburst Edit", "openai_gpt_image_25_sunburst_edit", "AtlasOpenAIGPTImage25SunburstEdit", "openai/gpt-image-2.5-sunburst/edit", True),
    ("AtlasCloud GPT Image-2.5 Flare Text-to-Image", "openai_gpt_image_25_flare_t2i", "AtlasOpenAIGPTImage25FlareTextToImage", "openai/gpt-image-2.5-flare/text-to-image", False),
    ("AtlasCloud GPT Image-2.5 Flare Edit", "openai_gpt_image_25_flare_edit", "AtlasOpenAIGPTImage25FlareEdit", "openai/gpt-image-2.5-flare/edit", True),
]


def _load(module_name, class_name):
    mod = importlib.import_module(f"src.atlascloud_comfyui.nodes.image.{module_name}")
    return getattr(mod, class_name)


@pytest.mark.parametrize("key,module_name,class_name,model_id,is_edit", GPT25_NODES)
def test_gpt25_metadata(key, module_name, class_name, model_id, is_edit):
    cls = _load(module_name, class_name)

    spec = cls.INPUT_TYPES()
    assert "atlas_client" in spec["required"]
    assert "prompt" in spec["required"]
    assert ("images" in spec["required"]) is is_edit
    assert ("mask" in spec["optional"]) is is_edit
    assert "xhigh" in spec["optional"]["quality"][0]
    assert "max" in spec["optional"]["quality"][0]

    assert cls.CATEGORY == "AtlasCloud/Image"
    assert cls.RETURN_TYPES == ("STRING", "STRING", "STRING")
    assert f'"model": "{model_id}"' in inspect.getsource(cls.run)


@pytest.mark.parametrize("key,module_name,class_name,model_id,is_edit", GPT25_NODES)
def test_gpt25_registered(key, module_name, class_name, model_id, is_edit):
    from src.atlascloud_comfyui.registry import (
        NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS,
    )

    assert key in NODE_CLASS_MAPPINGS
    assert key in NODE_DISPLAY_NAME_MAPPINGS
    assert NODE_CLASS_MAPPINGS[key].__name__ == class_name
