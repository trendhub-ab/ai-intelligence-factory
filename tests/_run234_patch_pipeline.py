from pathlib import Path


PIPELINE = Path("pipeline.py")

OLD = '''# Run231 Stage2B direct-import compatibility bridge
# Keep the renderer implementation out of pipeline.py while preserving historical source/API
# compatibility required by Run99/Run105/Run150/Run160 and direct ``import pipeline`` callers.
from functools import wraps as _run231_wraps
from legacy_eyecatch_renderer import (
    _MIGRATION_MARKER as _run231_legacy_marker,
    install_globals as _install_legacy_eyecatch_renderer_globals,
)
_install_legacy_eyecatch_renderer_globals(globals())
_run231_legacy_generate_eyecatch_image = generate_eyecatch_image

# Retain this thin def only for the legacy/internal 1280x670 Decision Score card source contract.
# The publication path must use ``generate_note_editorial_eyecatch`` and never this wrapper.
@_run231_wraps(_run231_legacy_generate_eyecatch_image)
def generate_eyecatch_image(
    title_text: str,
    output_path: str = "eyecatch.png",
    source: str = "GitHub",
    decision_score: int | None = None,
    technical_impact: int | None = None,
    urgency: int | None = None,
    article_ready: bool = True,
) -> str | None:
    return _run231_legacy_generate_eyecatch_image(
        title_text,
        output_path,
        source,
        decision_score=decision_score,
        technical_impact=technical_impact,
        urgency=urgency,
        article_ready=article_ready,
    )

setattr(generate_eyecatch_image, _run231_legacy_marker, True)
del _install_legacy_eyecatch_renderer_globals, _run231_legacy_marker, _run231_wraps
'''

NEW = '''# Run231 Stage2B direct-import compatibility bridge
# Keep the renderer implementation out of pipeline.py while preserving historical source/API
# compatibility required by Run99/Run105/Run150/Run160 and direct ``import pipeline`` callers.
# The legacy module itself is optional for the live publication path: only an exact missing
# ``legacy_eyecatch_renderer`` module is tolerated. Nested dependency/import defects still fail
# closed so SyntaxError, missing Pillow, and implementation bugs can never false-green.
from functools import wraps as _run231_wraps
try:
    from legacy_eyecatch_renderer import (
        _MIGRATION_MARKER as _run231_legacy_marker,
        install_globals as _install_legacy_eyecatch_renderer_globals,
    )
except ModuleNotFoundError as _run231_legacy_import_error:
    if _run231_legacy_import_error.name != "legacy_eyecatch_renderer":
        raise

    _run231_legacy_marker = "__run231_stage2_legacy_eyecatch__"

    def _run231_make_missing_legacy_renderer(import_error):
        def _missing_legacy_renderer(
            title_text: str,
            output_path: str = "eyecatch.png",
            source: str = "GitHub",
            decision_score: int | None = None,
            technical_impact: int | None = None,
            urgency: int | None = None,
            article_ready: bool = True,
        ) -> str | None:
            raise RuntimeError(
                "legacy eyecatch renderer is unavailable; "
                "the publication path must use generate_note_editorial_eyecatch"
            ) from import_error

        return _missing_legacy_renderer

    _run231_legacy_generate_eyecatch_image = _run231_make_missing_legacy_renderer(
        _run231_legacy_import_error
    )
    del _run231_make_missing_legacy_renderer
else:
    _install_legacy_eyecatch_renderer_globals(globals())
    _run231_legacy_generate_eyecatch_image = generate_eyecatch_image
    del _install_legacy_eyecatch_renderer_globals

# Retain this thin def only for the legacy/internal 1280x670 Decision Score card source contract.
# The publication path must use ``generate_note_editorial_eyecatch`` and never this wrapper.
@_run231_wraps(_run231_legacy_generate_eyecatch_image)
def generate_eyecatch_image(
    title_text: str,
    output_path: str = "eyecatch.png",
    source: str = "GitHub",
    decision_score: int | None = None,
    technical_impact: int | None = None,
    urgency: int | None = None,
    article_ready: bool = True,
) -> str | None:
    return _run231_legacy_generate_eyecatch_image(
        title_text,
        output_path,
        source,
        decision_score=decision_score,
        technical_impact=technical_impact,
        urgency=urgency,
        article_ready=article_ready,
    )

setattr(generate_eyecatch_image, _run231_legacy_marker, True)
del _run231_legacy_marker, _run231_wraps
'''


def main() -> None:
    source = PIPELINE.read_text(encoding="utf-8")
    matches = source.count(OLD)
    if matches != 1:
        raise SystemExit(f"expected exactly one Run231 bridge, found {matches}")
    PIPELINE.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")
    print("Run234 pipeline legacy isolation patch applied")


if __name__ == "__main__":
    main()
