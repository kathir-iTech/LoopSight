#!/usr/bin/env python3
"""
LoopSight — pre-commit secret scanner.

Scans staged files for likely secrets (API keys, tokens) and fails the
commit if any are found. Run it in three ways:

1. As a git pre-commit hook:
       python scripts/check_secrets.py        # scans staged files
2. Standalone against files:
       python scripts/check_secrets.py --files path1 path2 ...
3. Install as the repo pre-commit hook:
       python scripts/check_secrets.py --install

Patterns (deliberately broad — false positives are cheap; a leaked key is not):
  - AIza...                (Google API keys)
  - AQ.[A-Za-z0-9_-]{10,}  (this project's Gemini key prefix, seen in .env)
  - sk-[A-Za-z0-9]{16,}    (generic "sk-" secret keys, OpenAI-style)
  - -----BEGIN ... PRIVATE KEY-----  (PEM private keys)
  - AWS AKIA...            (AWS access key IDs)
  - "key" = literal assignment of a token

The scanner skips obviously non-secret lines (e.g. .env.example templates,
placeholder values like 'YOUR_KEY_HERE', empty values).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# --- Patterns -------------------------------------------------------------
# (name, regex) pairs. Regexes are searched as substring scans on each line.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{20,}")),
    ("gemini_aq_key", re.compile(r"AQ\.[0-9A-Za-z_\-]{15,}")),
    ("openai_sk_key", re.compile(r"\bsk-[0-9A-Za-z]{16,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"\b[0-9A-Za-z/+=]{40}\b")),
    ("pem_private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# Files that are intentionally allowed to contain key *shapes* (templates,
# fixtures, docs). Scanner will still scan them but only warn, not fail.
ALLOW_WARN_ONLY_EXT: set[str] = {".md", ".example", ".template"}

# Heuristic: a line is a real assignment if it has exactly one '=' and the
# value side is non-empty and not obviously a placeholder.
_PLACEHOLDER_VALUE = re.compile(r'^\s*(["\']?)(your|example|xxx|placeholder|none|changeme|\.\.\.)\1\s*$', re.I)


def _is_templated_file(path: Path) -> bool:
    return path.suffix in ALLOW_WARN_ONLY_EXT or ".example" in str(path).lower()


def _is_placeholder_value(line: str) -> bool:
    # Strip value after the LAST '=' (i.e. the value side)
    if "=" not in line:
        return True
    key, _, value = line.rpartition("=")
    value = value.strip().strip('"').strip("'")
    if not value:
        return True
    if _PLACEHOLDER_VALUE.search(value):
        return True
    # Known benign sentinels
    if value.lower() in ("true", "false", "0", "1", "null", "none", "local", "development", "production"):
        # Only treat as placeholder if it looks like a config flag, not a token.
        # Access/secret key bodies are 16-40 chars alnum + regex-matched above;
        # a short bare value after '=' is almost never a real secret.
        if len(value) < 16:
            return True
    return False


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """Return list of (pattern_name, line_number, line_snippet)."""
    findings: list[tuple[str, int, str]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        # Can't read; treat as suspicious but don't hard-fail the whole commit.
        return [("unreadable", 0, f"<could not read: {e}>")]
    for lineno, line in enumerate(lines, 1):
        if _is_placeholder_value(line):
            continue
        for name, rx in PATTERNS:
            if rx.search(line):
                findings.append((name, lineno, line.strip()[:120]))
    return findings


def _staged_files() -> list[Path]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return []
    files = []
    for name in out.stdout.splitlines():
        name = name.strip()
        if not name:
            continue
        p = Path(name)
        if p.exists():
            files.append(p)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="LoopSight pre-commit secret scanner")
    parser.add_argument("--files", nargs="*", default=None, help="explicit file paths to scan")
    parser.add_argument("--install", action="store_true", help="install as .git/hooks/pre-commit and exit")
    args = parser.parse_args()

    if args.install:
        hook = Path(__file__).resolve().parents[1] / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        # Write a shell wrapper that calls this python script
        script = (
            "#!/bin/sh\n"
            "# LoopSight — pre-commit secret scanner (auto-generated)\n"
            f'exec python "{Path(__file__).resolve()}"\n'
        )
        hook.write_text(script, encoding="utf-8")
        try:
            hook.chmod(0o755)
        except Exception:
            pass  # Windows: no-op; git runs hooks regardless
        print(f"[installed] pre-commit hook -> {hook}")
        return 0

    if args.files is not None:
        files = [Path(f) for f in args.files]
    else:
        files = _staged_files()

    if not files:
        print("[ok] no staged files to scan")
        return 0

    blocked = False
    warned = False
    for path in files:
        findings = scan_file(path)
        if not findings:
            continue
        templated = _is_templated_file(path)
        for name, lineno, snippet in findings:
            if templated:
                print(f"[warn ] {path}:{lineno} [{name}] {snippet}")
                warned = True
            else:
                print(f"[BLOCK] {path}:{lineno} [{name}] {snippet}")
                blocked = True

    if blocked:
        print("\n[FAIL] Possible secret(s) staged. Unstage or scrub them before committing.")
        print("       Review the files above. NEVER commit live API keys.")
        return 1
    if warned:
        print("\n[ok] only template/documentation matches (not blocking).")
    else:
        print("[ok] no secrets detected in staged files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
