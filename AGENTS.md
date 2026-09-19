# Project Instructions

DevConfig-Gen is a local, provider-based tool for generating and validating
structured JSON/YAML configuration. Keep the core provider-neutral and free of
side effects.

## Ground rules

- Do not add network, deployment, service-management, credential, or
  system-mutation behavior to the core engine.
- Keep the CLI thin: it must call the shared pipeline in
  `devconfig_gen.engine`, never re-implement generation logic.
- Every behavior change needs a test. Run the suite before finishing:

  ```bash
  PYTHONPATH=src python3 -m unittest discover -s tests -v
  ```

- Keep `README.md` and `ARCHITECTURE.md` accurate when the public API, CLI,
  formats, or provider contract changes.
- Do not publish packages, create releases, or push to a remote repository
  unless explicitly asked.
