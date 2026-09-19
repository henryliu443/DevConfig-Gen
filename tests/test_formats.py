import json
import tempfile
import unittest
from pathlib import Path

from devconfig_gen import formats


class TestJsonFormat(unittest.TestCase):
    def test_json_roundtrip(self):
        data = {"a": 1, "b": [True, None, "x"]}
        text = formats.dumps(data, "json")
        self.assertEqual(formats.loads(text, "json"), data)

    def test_json_dump_is_sorted_and_newline_terminated(self):
        text = formats.dumps({"b": 1, "a": 2}, "json")
        self.assertTrue(text.endswith("\n"))
        self.assertLess(text.index('"a"'), text.index('"b"'))

    def test_invalid_json_reports_format_error(self):
        with self.assertRaises(formats.FormatError) as ctx:
            formats.loads("{not json}", "json")
        self.assertIn("invalid JSON", str(ctx.exception))


class TestYamlFormat(unittest.TestCase):
    def test_scalar_types(self):
        data = formats.loads(
            "name: web\nport: 8080\nratio: 0.5\nenabled: true\nempty: null\n", "yaml"
        )
        self.assertEqual(
            data,
            {"name": "web", "port": 8080, "ratio": 0.5, "enabled": True, "empty": None},
        )

    def test_nested_mappings_and_sequences(self):
        text = (
            "service:\n"
            "  name: web\n"
            "  ports:\n"
            "    - 80\n"
            "    - 443\n"
            "  labels:\n"
            "    team: platform\n"
        )
        self.assertEqual(
            formats.loads(text, "yaml"),
            {
                "service": {
                    "name": "web",
                    "ports": [80, 443],
                    "labels": {"team": "platform"},
                }
            },
        )

    def test_sequence_of_mappings(self):
        text = "items:\n  - name: a\n    value: 1\n  - name: b\n    value: 2\n"
        self.assertEqual(
            formats.loads(text, "yaml"),
            {"items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]},
        )

    def test_flow_collections(self):
        data = formats.loads("tags: [a, b]\nmeta: {x: 1, y: [2, 3]}\n", "yaml")
        self.assertEqual(data, {"tags": ["a", "b"], "meta": {"x": 1, "y": [2, 3]}})

    def test_comments_and_blank_lines_are_ignored(self):
        data = formats.loads("# top\nname: web  # inline\n\nport: 80\n", "yaml")
        self.assertEqual(data, {"name": "web", "port": 80})

    def test_quoted_strings_are_preserved(self):
        data = formats.loads('a: "1"\nb: \'true\'\nc: "a: b"\n', "yaml")
        self.assertEqual(data, {"a": "1", "b": "true", "c": "a: b"})

    def test_literal_block_scalar(self):
        data = formats.loads("script: |\n  line one\n  line two\n", "yaml")
        self.assertEqual(data["script"], "line one\nline two\n")

    def test_invalid_indentation_reports_error(self):
        with self.assertRaises(formats.FormatError):
            formats.loads("a:\n    b: 1\n  c: 2\n", "yaml")

    def test_yaml_roundtrip(self):
        data = {
            "name": "web",
            "port": 8080,
            "labels": {"tier": "front end", "count": "3"},
            "items": [1, 2, {"nested": True}],
            "empty_list": [],
            "empty_map": {},
        }
        text = formats.dumps(data, "yaml")
        self.assertEqual(formats.loads(text, "yaml"), data)

    def test_dump_quotes_ambiguous_scalars(self):
        text = formats.dumps({"version": "1", "flag": "true", "note": ""}, "yaml")
        reloaded = formats.loads(text, "yaml")
        self.assertEqual(reloaded, {"version": "1", "flag": "true", "note": ""})


class TestFormatDetectionAndIO(unittest.TestCase):
    def test_detect_format_from_suffix(self):
        self.assertEqual(formats.detect_format(path="a.json"), "json")
        self.assertEqual(formats.detect_format(path="a.yaml"), "yaml")
        self.assertEqual(formats.detect_format(path="a.yml"), "yaml")

    def test_detect_format_from_content(self):
        self.assertEqual(formats.detect_format(text='{"a": 1}'), "json")
        self.assertEqual(formats.detect_format(text="a: 1"), "yaml")

    def test_loads_autodetects(self):
        self.assertEqual(formats.loads('{"a": 1}'), {"a": 1})
        self.assertEqual(formats.loads("a: 1"), {"a": 1})

    def test_load_data_accepts_text_and_path(self):
        self.assertEqual(formats.load_data("a: 1"), {"a": 1})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.yaml"
            path.write_text("a: 1\n", encoding="utf-8")
            self.assertEqual(formats.load_data(path), {"a": 1})
            self.assertEqual(formats.load_data(str(path)), {"a": 1})

    def test_dump_file_creates_parents(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "out.yaml"
            formats.dump_file({"a": 1}, target)
            self.assertEqual(formats.loads(target.read_text(), "yaml"), {"a": 1})

    def test_media_type_helpers(self):
        self.assertEqual(formats.media_type_for("json"), "application/json")
        self.assertEqual(formats.media_type_for("yaml"), "application/yaml")
        self.assertEqual(formats.format_from_media_type("application/yaml"), "yaml")

    def test_unsupported_format_raises(self):
        with self.assertRaises(formats.FormatError):
            formats.normalize_format("toml")

    def test_resolve_format_prefers_explicit_then_name(self):
        self.assertEqual(formats.resolve_format("yaml", name="x.json"), "yaml")
        self.assertEqual(formats.resolve_format(None, name="x.yml"), "yaml")
        self.assertEqual(formats.resolve_format(None, default="json"), "json")


if __name__ == "__main__":
    unittest.main()
