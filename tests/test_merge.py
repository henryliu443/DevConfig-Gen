import json
import tempfile
import unittest
from pathlib import Path

from devconfig_gen import build_request, generate_pipeline
from devconfig_gen import formats


class TestDeepMerge(unittest.TestCase):
    def test_nested_mappings_merge_with_overlay_winning(self):
        base = {"service": {"name": "a", "port": 80, "labels": {"team": "core", "tier": "api"}}}
        overlay = {"service": {"port": 8080, "labels": {"tier": "edge"}}}
        merged = formats.deep_merge(base, overlay)
        self.assertEqual(
            merged,
            {
                "service": {
                    "name": "a",
                    "port": 8080,
                    "labels": {"team": "core", "tier": "edge"},
                }
            },
        )

    def test_scalar_and_list_overlays_replace(self):
        self.assertEqual(formats.deep_merge({"a": 1}, {"a": 2}), {"a": 2})
        self.assertEqual(formats.deep_merge({"a": [1]}, {"a": [2, 3]}), {"a": [2, 3]})
        self.assertEqual(formats.deep_merge({"a": {"b": 1}}, {"a": 2}), {"a": 2})

    def test_inputs_are_not_mutated(self):
        base = {"service": {"labels": {"team": "core"}}}
        overlay = {"service": {"labels": {"tier": "edge"}}}
        formats.deep_merge(base, overlay)
        self.assertEqual(base, {"service": {"labels": {"team": "core"}}})
        self.assertEqual(overlay, {"service": {"labels": {"tier": "edge"}}})


class TestMultiSourceRequest(unittest.TestCase):
    def test_multiple_inputs_merge_left_to_right(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.yaml"
            override = Path(directory) / "prod.json"
            base.write_text(
                "service:\n  name: base\n  port: 80\n  labels:\n    team: core\n",
                encoding="utf-8",
            )
            override.write_text(
                json.dumps({"service": {"port": 9090, "labels": {"tier": "edge"}}}),
                encoding="utf-8",
            )
            request = build_request(input_path=[str(base), str(override)])
        self.assertEqual(
            request.context,
            {"service": {"name": "base", "port": 9090, "labels": {"team": "core", "tier": "edge"}}},
        )

    def test_overrides_apply_dotted_paths_last(self):
        request = build_request(
            context={"service": {"name": "web", "port": 80}},
            overrides={"service.port": "8080", "service.environment": "production"},
        )
        self.assertEqual(
            request.context,
            {"service": {"name": "web", "port": "8080", "environment": "production"}},
        )

    def test_generate_pipeline_merges_and_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.yaml"
            base.write_text("service:\n  name: web\n  port: 80\n", encoding="utf-8")
            result = generate_pipeline(
                "service",
                input_path=[str(base)],
                overrides={"service.port": "9090"},
                output_format="json",
            )
        service = result.artifacts[0].content["service"]
        self.assertEqual(service["port"], 9090)
        self.assertEqual(service["name"], "web")


if __name__ == "__main__":
    unittest.main()
