import unittest

from pydantic import ValidationError

from src.configs.application.local import LocalConfig


def config(reports, mappings=None):
    return {
        "system": {"db_path": "db.sqlite3"},
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


if __name__ == "__main__":
    unittest.main()
