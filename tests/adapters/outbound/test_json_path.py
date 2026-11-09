import unittest

from src.adapters.outbound.json_path import PathError, resolve

ROOT = {
    "start": "t0",
    "stats": [
        {"name": "a", "p0.9": 1, "count": 10},
        {"name": "b", "p0.9": 2, "count": 20},
        {"name": "Total", "p0.9": 3, "count": 30},
    ],
}


class ResolveTests(unittest.TestCase):
    def test_keys_indexes_and_quoted_keys(self):
        self.assertEqual(resolve("start", ROOT, ROOT), "t0")
        self.assertEqual(resolve('stats[1]["p0.9"]', ROOT, ROOT), 2)

    def test_equality_filter_selects_single_item(self):
        self.assertEqual(resolve("stats[name=Total].count", ROOT, ROOT), 30)

    def test_inequality_filter_returns_remaining_items(self):
        items = resolve("stats[name!=Total]", ROOT, ROOT)
        assert isinstance(items, list)
        names = [item["name"] for item in items]
        self.assertEqual(names, ["a", "b"])

    def test_root_prefix_and_item_reference(self):
        item = {"name": "b"}
        self.assertEqual(resolve("$.start", item, ROOT), "t0")
        self.assertEqual(resolve('$.stats[name=@name]["p0.9"]', item, ROOT), 2)

    def test_errors(self):
        for path, message in (
            ("missing", "Key 'missing' not found"),
            ("stats[name=zzz]", "found 0"),
            ("stats[9]", "out of range"),
            ("start[0]", "Expected a list"),
            ("stats[", "Invalid path syntax"),
        ):
            with self.subTest(path=path), self.assertRaisesRegex(PathError, message):
                resolve(path, ROOT, ROOT)


if __name__ == "__main__":
    unittest.main()
