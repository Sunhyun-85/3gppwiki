#!/usr/bin/env python3
"""Build a deterministic, data-free source release archive."""
from __future__ import annotations

import argparse
import hashlib
import re
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = (
    ".cline",
    ".env.example",
    ".gitignore",
    "AGENTS.md",
    "Dockerfile",
    "README.md",
    "config.example.yaml",
    "docker-compose.yml",
    "docs",
    "prompts",
    "pyproject.toml",
    "ranwiki",
    "scripts",
    "src",
    "tests",
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def version() -> str:
    return str(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])


def release_files() -> list[Path]:
    files: list[Path] = []
    for name in TOP_LEVEL:
        path = ROOT / name
        candidates = path.rglob("*") if path.is_dir() else (path,)
        for candidate in candidates:
            relative = candidate.relative_to(ROOT)
            if (candidate.is_file() and not EXCLUDED_PARTS.intersection(relative.parts)
                    and candidate.suffix not in EXCLUDED_SUFFIXES):
                files.append(relative)
    return sorted(set(files), key=lambda item: item.as_posix())


def validate(files: list[Path]) -> None:
    forbidden = {".env", "config.yaml", "ran2wiki.db"}
    for relative in files:
        if relative.name in forbidden or relative.parts[0] in {"data", ".devdeps", ".git"}:
            raise ValueError(f"forbidden release file: {relative}")
        payload = (ROOT / relative).read_bytes()
        for pattern in SECRET_PATTERNS:
            if pattern.search(payload):
                raise ValueError(f"possible credential in release file: {relative}")


def build(output_dir: Path) -> tuple[Path, Path]:
    release_version = version()
    prefix = f"ranwiki-v{release_version}"
    archive = output_dir / f"{prefix}.zip"
    checksum = output_dir / "SHA256SUMS"
    files = release_files()
    validate(files)
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative in files:
            info = zipfile.ZipInfo(f"{prefix}/{relative.as_posix()}", (2024, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if relative.as_posix() == "ranwiki" else 0o644) << 16
            bundle.writestr(info, (ROOT / relative).read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    archive, checksum = build(args.output_dir)
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
