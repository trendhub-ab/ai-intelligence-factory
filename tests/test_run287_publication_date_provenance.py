from __future__ import annotations

import re
import types
import unittest
from pathlib import Path

import run287_publication_date_provenance as run287

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production_pipeline.py"
PUBLICATION = ROOT / "publication_contract.py"
NOTE_READY = ROOT / ".github" / "workflows" / "note-ready-sync.yml"


def _date_parser(value):
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(value or ""))
    return match.group(1) if match else ""


def _original_header(summary, repo_name, repo_url, source="GitHub", published_at=None):
    lines = [
        "### 元情報",
        f"- **主一次情報**: [{repo_name}]({repo_url})",
        f"- **発見経路**: {source}",
    ]
    published = _date_parser(published_at)
    if published:
        lines.append(f"- **公開・更新**: {published}")
    return "\n".join(lines)


class Run287PublicationDateProvenanceTests(unittest.TestCase):
    def _fixture(self):
        note = types.SimpleNamespace(
            build_reader_first_header=_original_header,
            _reader_published_date=_date_parser,
        )
        pipeline = types.SimpleNamespace(build_reader_first_header=_original_header)
        return note, pipeline

    def test_netflix_hn_discovery_date_never_masquerades_as_primary_publication_date(self):
        note, pipeline = self._fixture()
        run287.install(note, pipeline)
        header = note.build_reader_first_header(
            {},
            "GenRec: Towards LLM-Native Recommendation at Netflix",
            "https://netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3",
            "HackerNews",
            "2026-08-15T12:34:56+00:00",
        )
        self.assertNotIn("**公開・更新**: 2026-08-15", header)
        self.assertIn("**Hacker News投稿日**: 2026-08-15", header)
        self.assertIs(pipeline.build_reader_first_header, note.build_reader_first_header)

    def test_non_hn_source_keeps_existing_publication_label_contract(self):
        note, pipeline = self._fixture()
        run287.install(note, pipeline)
        header = note.build_reader_first_header({}, "Paper", "https://arxiv.org/abs/1", "ArXiv", "2026-08-10")
        self.assertIn("**公開・更新**: 2026-08-10", header)
        self.assertNotIn("Hacker News投稿日", header)

    def test_empty_hn_timestamp_adds_no_fabricated_date(self):
        note, _ = self._fixture()
        run287.install(note)
        header = note.build_reader_first_header({}, "Source", "https://example.com", "HackerNews", None)
        self.assertNotIn("公開・更新", header)
        self.assertNotIn("Hacker News投稿日", header)

    def test_install_is_idempotent(self):
        note, pipeline = self._fixture()
        run287.install(note, pipeline)
        wrapped = note.build_reader_first_header
        run287.install(note, pipeline)
        self.assertIs(note.build_reader_first_header, wrapped)
        self.assertIs(pipeline.build_reader_first_header, wrapped)

    def test_repository_tracks_run287_as_publication_surface(self):
        production = PRODUCTION.read_text(encoding="utf-8")
        publication = PUBLICATION.read_text(encoding="utf-8")
        note_ready = NOTE_READY.read_text(encoding="utf-8")
        self.assertIn("install_run287_publication_date_provenance", production)
        self.assertIn('"run287_publication_date_provenance.py"', publication)
        self.assertIn("run287_publication_date_provenance.py", note_ready)
        self.assertIn("tests.test_run287_publication_date_provenance", note_ready)

    def test_module_has_no_provider_network_or_persistence_surface(self):
        text = (ROOT / "run287_publication_date_provenance.py").read_text(encoding="utf-8")
        for forbidden in ("google.genai", "GEMINI_API_KEY", "requests.", "NOTION_API_KEY", "http://", "https://"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
