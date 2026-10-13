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


def test_incomplete_public_title_fails_closed_before_eyecatch_generation():
    incomplete_titles = (
        "OpenAIの「歴史を塗り替える数学的発見」は、",
        "新モデルの評価結果が、",
        "導入効果は高いけれど、",
        "性能は改善した。しかし、",
    )
    for title in incomplete_titles:
        try:
            contract.require_public_title({"title_text": title})
        except contract.EyecatchContractError:
            pass
        else:
            raise AssertionError(f"incomplete public title must fail closed: {title}")


def test_policy_hash_covers_run248_quality_calibration():
    assert "run248_first_real_publish_quality_calibration.py" in contract.POLICY_FILES


def test_headline_pnginfo_rejects_incomplete_headline_before_save():
    public_title = "AIを「使う仕事」から「AIに任せる仕事」へ"
    incomplete_headlines = (
        "AIの仕事は、",
        "導入効果が、",
        "価値は高いけれど、",
        "性能は改善した。しかし、",
    )
    for headline in incomplete_headlines:
        try:
            contract.headline_pnginfo(public_title, headline, [headline])
        except contract.EyecatchContractError:
            pass
        else:
            raise AssertionError(f"incomplete PNG headline must fail before save: {headline}")


def test_saved_png_with_incomplete_headline_fails_closed(tmp_path):
    import base64
    import zlib

    from PIL import Image, PngImagePlugin

    public_title = "AIを「使う仕事」から「AIに任せる仕事」へ"
    incomplete_headlines = (
        "AIの仕事は、",
        "導入効果が、",
        "価値は高いけれど、",
        "性能は改善した。しかし、",
    )
    encoded_mask = base64.b64encode(zlib.compress(b"\x01" * 9)).decode("ascii")

    for index, headline in enumerate(incomplete_headlines):
        image = Image.new("RGB", (1280, 670), "white")
        for x in range(3):
            for y in range(3):
                image.putpixel((x, y), (0, 0, 0))

        info = PngImagePlugin.PngInfo()
        info.add_text("aiif_public_title_sha256", contract.title_sha256(public_title))
        info.add_text("aiif_expected_headline", headline)
        info.add_text("aiif_rendered_headline", headline)
        info.add_text(
            "aiif_headline_ink_v1",
            json.dumps([[0, 0, 3, 3, [0, 0, 0], encoded_mask]], separators=(",", ":")),
        )
        path = tmp_path / f"incomplete-{index}.png"
        image.save(path, pnginfo=info)

        try:
            contract.verify_image_headline(path, public_title)
        except contract.EyecatchContractError:
            pass
        else:
            raise AssertionError(f"incomplete saved PNG headline must fail closed: {headline}")


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
