import json
from pathlib import Path

import eyecatch_publication_contract as contract


def test_public_title_is_required_and_never_inferred_from_source_name():
    assert contract.require_public_title({"title_text": "VT Code：AIのコード変更をどう確認する？"}) == "VT Code：AIのコード変更をどう確認する？"
    try:
        contract.require_public_title({"title_text": ""})
    except contract.EyecatchContractError:
        pass
    else:
        raise AssertionError("missing public title must fail closed")


def test_versioned_filename_is_bound_to_title_and_current_policy():
    title = "VT Code：AIのコード変更をどう確認する？"
    filename = contract.versioned_image_filename("Show_HN_VT_Code.png", title)
    assert filename.startswith("Show_HN_VT_Code__ecv1_")
    assert filename.endswith(".png")
    url = "https://raw.githubusercontent.com/example/repo/main/eyecatch_images/" + filename
    assert contract.current_asset_url(url, title)
    assert not contract.current_asset_url(url, "別の公開タイトル")


def test_manifest_binds_policy_title_and_image_bytes(tmp_path):
    title = "VT Code：AIのコード変更をどう確認する？"
    image = tmp_path / "cover.png"
    image.write_bytes(b"fake-png-bytes-for-contract-test")
    manifest = contract.build_manifest(title, image)
    assert contract.validate_manifest_metadata(manifest, title)
    assert contract.validate_manifest(manifest, title, image)

    image.write_bytes(b"changed-image-bytes")
    assert not contract.validate_manifest(manifest, title, image)


def test_manifest_url_is_adjacent_to_image():
    image = "https://raw.githubusercontent.com/example/repo/main/eyecatch_images/a__ecv1_0123456789abcdef.png"
    assert contract.manifest_url(image) == image + ".json"
