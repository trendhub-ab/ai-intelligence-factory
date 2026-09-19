"""Run287: publication-date provenance precision.

Hacker News acquisition timestamps describe the HN post/discovery event, not the
publication/update date of an external primary source. Keep that useful date visible,
but label it honestly so a discovery timestamp can never masquerade as primary-source
publication metadata.

This is deterministic, provider-free, and publication-surface affecting.
"""
from __future__ import annotations

from typing import Any


def install(note_manuscript_module: Any, pipeline_module: Any | None = None) -> None:
    if bool(getattr(note_manuscript_module, "_run287_publication_date_provenance_installed", False)):
        if pipeline_module is not None:
            pipeline_module.build_reader_first_header = note_manuscript_module.build_reader_first_header
        return

    original = getattr(note_manuscript_module, "build_reader_first_header", None)
    date_parser = getattr(note_manuscript_module, "_reader_published_date", None)
    if not callable(original) or not callable(date_parser):
        raise RuntimeError("Run287 requires note_manuscript reader header/date helpers")

    def build_reader_first_header(
        reader_summary,
        repo_name,
        repo_url,
        source="GitHub",
        published_at=None,
        include_source=True,
    ):
        source_name = str(source or "").strip()

        def render(date_value):
            # Preserve compatibility with historical header builders while allowing the current
            # public-manuscript path to suppress duplicated top provenance.
            if include_source:
                return original(reader_summary, repo_name, repo_url, source, date_value)
            return original(
                reader_summary, repo_name, repo_url, source, date_value,
                include_source=False,
            )

        if source_name != "HackerNews":
            return render(published_at)

        # HN `published_at` comes from the Hacker News item timestamp. It is not
        # evidence for when an external primary article itself was published/updated.
        header = render(None)
        hn_date = date_parser(published_at)
        if not include_source or not header or not repo_url or not hn_date:
            return header
        return f"{header}\n- **Hacker News投稿日**: {hn_date}"

    note_manuscript_module.build_reader_first_header = build_reader_first_header
    setattr(note_manuscript_module, "_run287_publication_date_provenance_installed", True)
    setattr(note_manuscript_module, "_run287_original_build_reader_first_header", original)
    if pipeline_module is not None:
        pipeline_module.build_reader_first_header = build_reader_first_header
