from member_presentation_sync import _member_presentation_title


def test_anything_llm_uses_member_friendly_display_name():
    assert _member_presentation_title(
        "github:mintplex-labs/anything-llm",
        "Mintplex-Labs/anything-llm",
    ) == "AnythingLLM"


def test_other_titles_are_unchanged_without_an_explicit_override():
    assert _member_presentation_title(
        "github:langgenius/dify",
        "langgenius/dify",
    ) == "langgenius/dify"
