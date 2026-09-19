import json
import tempfile
import unittest
from pathlib import Path

from devconfig_gen import generate_from_file, generate_pipeline, load_file

from _support import EXAMPLES, run_cli

SAMPLE = str(EXAMPLES / "custom.yaml")


class TestApiCliParity(unittest.TestCase):
    def _cli_output(self, output_format):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        result = run_cli(
            "generate",
            "--provider",
            "custom",
            "--input",
            SAMPLE,
            "--output-dir",
            directory.name,
            "--format",
            output_format,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        suffix = "yaml" if output_format == "yaml" else "json"
        return Path(directory.name) / f"custom.{suffix}"

    def test_cli_json_matches_python_api_byte_for_byte(self):
        cli_path = self._cli_output("json")
        with tempfile.TemporaryDirectory() as directory:
            generate_from_file("custom", SAMPLE, output_dir=directory, output_format="json")
            api_path = Path(directory) / "custom.json"
            self.assertEqual(cli_path.read_bytes(), api_path.read_bytes())

    def test_cli_yaml_matches_python_api_byte_for_byte(self):
        cli_path = self._cli_output("yaml")
        with tempfile.TemporaryDirectory() as directory:
            generate_from_file("custom", SAMPLE, output_dir=directory, output_format="yaml")
            api_path = Path(directory) / "custom.yaml"
            self.assertEqual(cli_path.read_bytes(), api_path.read_bytes())

    def test_generate_from_file_matches_pipeline_with_loaded_context(self):
        context = load_file(SAMPLE)
        with tempfile.TemporaryDirectory() as directory:
            from_file = generate_from_file(
                "custom", SAMPLE, output_dir=directory, output_format="json"
            )
        from_pipeline = generate_pipeline(
            "custom", context=context, output_format="json"
        )
        self.assertEqual(
            from_file.artifacts[0].content, from_pipeline.artifacts[0].content
        )

    def test_json_and_yaml_outputs_describe_the_same_document(self):
        json_path = self._cli_output("json")
        yaml_path = self._cli_output("yaml")
        self.assertEqual(
            json.loads(json_path.read_text(encoding="utf-8")),
            load_file(yaml_path),
        )


if __name__ == "__main__":
    unittest.main()
