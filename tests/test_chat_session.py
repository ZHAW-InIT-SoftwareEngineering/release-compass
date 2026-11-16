import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.adapters.outbound.ontology.turtle_knowledge_base import (
    FACTS_FILE,
    TurtleKnowledgeBase,
)
from src.chat_session import build_chat_session
from src.configs.application.local import LocalConfig

EXAMPLE_REPORT = Path(
    "data/raw/reports/example_reports/TeaStoreReports/Locust/Locust_TeaStore_Report_Original.html"
)
LOCUST_MAPPING = Path("configs/ingestion/locust.yaml")


class BuildChatSessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.kb_dir = Path(directory.name) / "kb"

    def build(self, reports):
        config = LocalConfig.model_validate(
            {
                "system": {"kb_dir": self.kb_dir},
                "ingestion": {"mappings": {"locust": LOCUST_MAPPING}},
                "data": {"reports": reports},
            }
        )
        with patch("src.chat_session.load_local_config", return_value=config):
            return build_chat_session()

    def test_imports_into_knowledge_base_and_stops_before_assessment(self):
        session = self.build([{"path": EXAMPLE_REPORT, "source": "locust"}])

        self.assertIsNone(session)
        self.assertTrue((self.kb_dir / FACTS_FILE).exists())
        rows = TurtleKnowledgeBase(self.kb_dir).select(
            "SELECT ?report WHERE { ?report a release-compass:Report }"
        )
        self.assertEqual(len(rows), 1)

    def test_requires_a_stored_report(self):
        with self.assertRaisesRegex(ValueError, "At least one stored report"):
            self.build([])


if __name__ == "__main__":
    unittest.main()
