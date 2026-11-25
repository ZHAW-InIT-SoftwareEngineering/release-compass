import unittest

from pydantic import ValidationError

from src.configs.application.local import LocalConfig


def config(reports, mappings=None, system=None):
    return {
        "system": system or {"kb_dir": "data/kb"},
        "ingestion": {"mappings": mappings or {"locust": "locust.yaml"}},
        "data": {"reports": reports},
    }


class LocalConfigTests(unittest.TestCase):
    def test_accepts_reports_with_configured_source(self):
        local = LocalConfig.model_validate(
            config([{"path": "report.html", "source": "locust"}])
        )
        self.assertEqual(local.data.reports[0].source, "locust")

    def test_requires_report_source(self):
        with self.assertRaisesRegex(ValidationError, "source"):
            LocalConfig.model_validate(config([{"path": "report.html"}]))

    def test_rejects_source_without_mapping(self):
        with self.assertRaisesRegex(ValidationError, "'mocha' without"):
            LocalConfig.model_validate(
                config([{"path": "report.html", "source": "mocha"}])
            )

    def test_store_defaults_to_knowledge_base(self):
        local = LocalConfig.model_validate(config([]))
        self.assertEqual(local.system.store, "knowledge_base")

    def test_llm_defaults_to_openrouter(self):
        local = LocalConfig.model_validate(config([]))
        self.assertEqual(str(local.system.llm), "configs/llm/openrouter.yaml")

    def test_accepts_selected_llm_config(self):
        local = LocalConfig.model_validate(
            config([], system={"kb_dir": "data/kb", "llm": "configs/llm/sglang.yaml"})
        )
        self.assertEqual(str(local.system.llm), "configs/llm/sglang.yaml")

    def test_selected_store_requires_its_path(self):
        with self.assertRaisesRegex(ValidationError, "requires system.db_path"):
            LocalConfig.model_validate(
                config([], system={"store": "sqlite", "kb_dir": "data/kb"})
            )
        local = LocalConfig.model_validate(
            config([], system={"store": "sqlite", "db_path": "x.sqlite3"})
        )
        self.assertEqual(str(local.system.db_path), "x.sqlite3")


if __name__ == "__main__":
    unittest.main()
