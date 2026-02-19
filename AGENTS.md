# Repository Guidelines

## Project Structure & Module Organization
This repository is currently minimal and centered on documentation.
- `README.md`: project overview and contribution intent.
- `.gitignore`: shared ignore rules.
- `.claude/`: local assistant/tooling settings.

As code is added, keep structure predictable:
- `src/` for application or library code.
- `tests/` for automated tests mirroring `src/` paths.
- `docs/` for design notes, ADRs, and longer guides.

Example: `src/auth/session.py` should have related tests in `tests/auth/test_session.py`.

## Build, Test, and Development Commands
There is no build pipeline yet. Keep local checks simple and reproducible.
- `git status` - verify only intended files changed.
- `git diff --staged` - review exactly what will be committed.
- `git log --oneline -n 10` - inspect recent commit style before writing yours.

When introducing a language/toolchain, add explicit commands to `README.md` and this file (for example `make test`, `npm test`, or `pytest`).

## Coding Style & Naming Conventions
No formatter/linter is enforced yet; keep contributions consistent and easy to review.
- Use clear, descriptive names (`user_profile_service`, not `ups`).
- Prefer small modules with single responsibilities.
- Use snake_case for files and directories unless a language ecosystem requires otherwise.
- Keep Markdown concise, with short sections and actionable wording.

If you add tooling (formatter/linter), document install and run steps in the same PR.

## Testing Guidelines
Automated tests are not configured yet. New features should include tests whenever practical.
- Place tests under `tests/`, mirroring source layout.
- Name tests by behavior (example: `test_rejects_invalid_token`).
- Include manual verification notes in PRs until automated test commands are standardized.

## Commit & Pull Request Guidelines
Current history is short (`Initial commit`), so follow a simple, consistent pattern.
- Commit message format: imperative, concise subject line (example: `Add contributor guide`).
- Keep commits focused; avoid mixing refactors with unrelated changes.
- PRs should include: objective, key changes, validation steps, and linked issue (if any).
- Add screenshots or terminal output when changes affect UX/CLI behavior.
