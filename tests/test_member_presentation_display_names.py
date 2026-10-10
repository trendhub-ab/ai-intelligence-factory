import pytest

from member_presentation_sync import _member_presentation_title


@pytest.mark.parametrize(
    ("sync_id", "source_name", "expected"),
    [
        ("github:langgenius/dify", "langgenius/dify", "Dify"),
        ("github:mintplex-labs/anything-llm", "Mintplex-Labs/anything-llm", "AnythingLLM"),
        ("github:browser-use/browser-use", "browser-use/browser-use", "browser-use"),
        ("github:comfyanonymous/comfyui", "comfyanonymous/ComfyUI", "ComfyUI"),
        ("github:cline/cline", "cline/cline", "Cline"),
    ],
)
def test_quick_links_use_member_friendly_display_names(sync_id, source_name, expected):
    assert _member_presentation_title(sync_id, source_name) == expected


def test_other_titles_are_unchanged_without_an_explicit_override():
    assert _member_presentation_title(
        "github:huggingface/datasets",
        "huggingface/datasets",
    ) == "huggingface/datasets"
