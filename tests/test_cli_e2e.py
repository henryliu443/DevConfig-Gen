import json
import tempfile
import unittest
from pathlib import Path

from devconfig_gen import load_file

from _support import EXAMPLES, run_cli

SAMPLE_JSON = str(EXAMPLES / "service.json")
SAMPLE_YAML = str(EXAMPLES / "service.yaml")


class TestCliEndToEnd(unittest.TestCase):
    def test_providers_lists_builtins(self):
        result = run_cli("providers")
        self.assertEqual(result.returncode, 0, result.stderr)
        names = result.stdout.split()
        self.assertIn("json", names)
        self.assertIn("service", names)

    def test_generate_service_json_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(
                "generate",
                "--provider",
                "service",
                "--input",
                SAMPLE_JSON,
                "--output-dir",
                directory,
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("generated", result.stdout)
            output = Path(directory) / "service.json"
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["service"]["name"], "checkout-api")
            self.assertEqual(data["service"]["port"], 8080)

    def test_generate_service_yaml_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(
                "generate",
                "--provider",
                "service",
                "--input",
                SAMPLE_YAML,
                "--output-dir",
                directory,
                "--format",
                "yaml",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(directory) / "service.yaml"
            data = load_file(output)
            self.assertEqual(data["service"]["environment"], "production")

    def test_generate_infers_format_from_name(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(
                "generate",
                "--provider",
                "service",
                "--input",
                SAMPLE_YAML,
                "--output-dir",
                directory,
                "--name",
                "custom.yaml",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / "custom.yaml").exists())

    def test_validate_valid_input_exits_zero(self):
        result = run_cli("validate", "--provider", "service", "--input", SAMPLE_YAML)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("valid", result.stdout)

    def test_validate_invalid_input_exits_one_with_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.yaml"
            bad.write_text("service:\n  name: web\n  port: 99999\n", encoding="utf-8")
            result = run_cli("validate", "--provider", "service", "--input", str(bad))
            self.assertEqual(result.returncode, 1)
            self.assertIn("port must be between 1 and 65535", result.stderr)

    def test_unknown_provider_exits_two(self):
        result = run_cli(
            "generate",
            "--provider",
            "missing",
            "--input",
            SAMPLE_JSON,
            "--output-dir",
            "out",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown provider", result.stderr)

    def test_missing_input_file_exits_two(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(
                "generate",
                "--provider",
                "service",
                "--input",
                str(Path(directory) / "absent.json"),
                "--output-dir",
                directory,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("error:", result.stderr)

    def test_schema_prints_json_steps(self):
        result = run_cli("schema", "--provider", "service")
        self.assertEqual(result.returncode, 0, result.stderr)
        steps = json.loads(result.stdout)
        self.assertEqual([step["id"] for step in steps], ["identity", "runtime", "metadata"])
        field_names = [field["name"] for step in steps for field in step["fields"]]
        self.assertIn("service.port", field_names)

    def test_validate_json_reports_structured_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.yaml"
            bad.write_text("service:\n  name: web\n  port: 99999\n", encoding="utf-8")
            result = run_cli(
                "validate", "--provider", "service", "--input", str(bad), "--json"
            )
            self.assertEqual(result.returncode, 1)
            diagnostics = json.loads(result.stdout)
            self.assertEqual(diagnostics[0]["field"], "service.port")
            self.assertEqual(diagnostics[0]["severity"], "error")

    def test_validate_json_on_valid_input_is_empty(self):
        result = run_cli(
            "validate", "--provider", "service", "--input", SAMPLE_YAML, "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_unknown_provider_schema_exits_two(self):
        result = run_cli("schema", "--provider", "missing")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown provider", result.stderr)

    def test_init_help_exits_zero(self):
        result = run_cli("init", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Run interactive terminal wizard", result.stdout)

    def test_ui_help_exits_zero(self):
        result = run_cli("ui", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Launch local configuration studio WebUI", result.stdout)
        self.assertIn("--workspace", result.stdout)


if __name__ == "__main__":
    unittest.main()
