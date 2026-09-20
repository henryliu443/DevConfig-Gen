# Project Instructions

DevConfig-Gen is a local, provider-based tool for generating and validating
structured JSON/YAML configuration. Keep the core provider-neutral and free of
side effects.

## Repo relationship (父/子)

- **This repo is the PARENT (父仓库 / upstream).**
- **Child (子仓库 / fork):** `DevConfig-Gen_SingBox` — a private integration
  fork derived from this repo.
- **Downstream legacy source (not a fork):** `Automated-sing-box-json-generator`
  — scheduled to be **merged/decoupled and retired**. It is **reference only**;
  never a development target. Do not develop there.

Authority flows **parent → child → downstream**:

- The parent owns the neutral core and the provider standard
  (`PROVIDER_STANDARD.md`).
- Domain-specific providers (e.g. `providers/singbox/`) live in the **child**,
  never here.
- The child must not fork or diverge the neutral core; core changes are made
  here first and flow down.

## Ground rules

- Follow `PROVIDER_STANDARD.md` (the DevConfig-Gen provider iron standard /
  white paper) for any "rich domain" (transformation) provider: zero side
  effects, pluggable variant isolation, no upstream version chasing, and
  explicit credentials-as-input. Read it before adding or changing a provider.
- Do not add network, deployment, service-management, credential, or
  system-mutation behavior to the core engine.
- Keep the CLI and the `init`/`ui` clients thin: they must call the shared
  pipeline in `devconfig_gen.engine`, never re-implement generation logic.
- Keep output deterministic: JSON and YAML preserve insertion order, so
  generated artifacts stay byte-for-byte stable.
- Every behavior change needs a test. Run the suite before finishing:

  ```bash
  PYTHONPATH=src python3 -m unittest discover -s tests -v
  ```

- Keep `README.md` and `ARCHITECTURE.md` accurate when the public API, CLI,
  formats, or provider contract changes.
- Do not publish packages, create releases, or push to a remote repository
  unless explicitly asked.
