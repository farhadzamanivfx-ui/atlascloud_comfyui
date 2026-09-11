"""Metadata-only tests for the 3D nodes added 2026-08-30.

New models: Seed3D 2.0, Hunyuan3D Rapid/Pro, Tripo H3.1 (text- and image-to-3D),
plus the AtlasCloud Download 3D Model utility.
These tests MUST NOT require ATLASCLOUD_API_KEY.
"""

import inspect

import pytest

THREE_D_NODES = [
    (
        "AtlasCloud Seed3D 2.0 Image-to-3D",
        "bytedance_seed3d_v20_image_to_3d",
        "AtlasSeed3DV20ImageTo3D",
        "bytedance/seed3d-v2.0/image-to-3d",
        "image",
    ),
    (
        "AtlasCloud Hunyuan3D Rapid Image-to-3D",
        "tencent_hunyuan3d_rapid_image_to_3d",
        "AtlasHunyuan3DRapidImageTo3D",
        "tencent/hunyuan3d-rapid/image-to-3d",
        "image",
    ),
    (
        "AtlasCloud Hunyuan3D Rapid Text-to-3D",
        "tencent_hunyuan3d_rapid_text_to_3d",
        "AtlasHunyuan3DRapidTextTo3D",
        "tencent/hunyuan3d-rapid/text-to-3d",
        "prompt",
    ),
    (
        "AtlasCloud Hunyuan3D Pro Image-to-3D",
        "tencent_hunyuan3d_pro_image_to_3d",
        "AtlasHunyuan3DProImageTo3D",
        "tencent/hunyuan3d-pro/image-to-3d",
        "image",
    ),
    (
        "AtlasCloud Hunyuan3D Pro Text-to-3D",
        "tencent_hunyuan3d_pro_text_to_3d",
        "AtlasHunyuan3DProTextTo3D",
        "tencent/hunyuan3d-pro/text-to-3d",
        "prompt",
    ),
    (
        "AtlasCloud Tripo H3.1 Text-to-3D",
        "tripo_h31_text_to_3d",
        "AtlasTripoH31TextTo3D",
        "tripo-h3.1/text-to-3d",
        "prompt",
    ),
    (
        "AtlasCloud Tripo H3.1 Image-to-3D",
        "tripo_h31_image_to_3d",
        "AtlasTripoH31ImageTo3D",
        "tripo-h3.1/image-to-3d",
        "image_url",
    ),
]


def _load(module_name, class_name):
    import importlib

    mod = importlib.import_module(f"src.atlascloud_comfyui.nodes.three_d.{module_name}")
    return getattr(mod, class_name)


@pytest.mark.parametrize("key,module_name,class_name,model_id,primary_input", THREE_D_NODES)
def test_3d_node_metadata(key, module_name, class_name, model_id, primary_input):
    cls = _load(module_name, class_name)

    spec = cls.INPUT_TYPES()
    required = spec["required"]
    assert "atlas_client" in required
    assert primary_input in required

    assert cls.CATEGORY == "AtlasCloud/3D"
    assert cls.RETURN_TYPES == ("STRING", "STRING")
    assert cls.RETURN_NAMES == ("model_url", "prediction_id")
    assert f'"model": "{model_id}"' in inspect.getsource(cls.run)


@pytest.mark.parametrize("key,module_name,class_name,model_id,primary_input", THREE_D_NODES)
def test_3d_nodes_registered(key, module_name, class_name, model_id, primary_input):
    from src.atlascloud_comfyui.registry import (
        NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS,
    )

    assert key in NODE_CLASS_MAPPINGS
    assert key in NODE_DISPLAY_NAME_MAPPINGS
    assert NODE_CLASS_MAPPINGS[key].__name__ == class_name


def test_download_model_3d_metadata():
    from src.atlascloud_comfyui.nodes.utils.download_model_3d import AtlasDownloadModel3D
    from src.atlascloud_comfyui.registry import (
        NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS,
    )

    spec = AtlasDownloadModel3D.INPUT_TYPES()
    assert "model_url" in spec["required"]
    assert AtlasDownloadModel3D.CATEGORY == "AtlasCloud/Utils"
    assert AtlasDownloadModel3D.RETURN_NAMES == ("model_file", "local_path")

    key = "AtlasCloud Download 3D Model"
    assert key in NODE_CLASS_MAPPINGS
    assert key in NODE_DISPLAY_NAME_MAPPINGS


def test_3d_nodes_reject_blank_prompt_and_image():
    from src.atlascloud_comfyui.nodes.three_d._common import resolve_image

    class _Client:
        def resolve_reference_images(self, refs):
            return list(refs)

    with pytest.raises(RuntimeError):
        resolve_image(_Client(), "   ")

    cls = _load("tencent_hunyuan3d_rapid_text_to_3d", "AtlasHunyuan3DRapidTextTo3D")
    with pytest.raises(RuntimeError):
        cls().run(atlas_client=None, prompt="  ")
