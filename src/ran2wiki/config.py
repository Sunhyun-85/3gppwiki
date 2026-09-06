from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ScopeConfig:
    group: str = "RAN2"
    include_rel20: bool = True
    include_6g: bool = True
    start_meeting: str = "125"
    end_meeting: str | None = None


@dataclass(frozen=True)
class PathsConfig:
    data_dir: Path = Path("data")
    database: Path = Path("data/db/ran2wiki.db")


@dataclass(frozen=True)
class SourceConfig:
    base_url: str = "https://www.3gpp.org/ftp/tsg_ran/WG2_RL2"
    download_base_url: str = "https://ftp.3gpp.org/tsg_ran/WG2_RL2"
    timeout_seconds: int = 60
    recent_meetings_to_recheck: int = 3
    download_workers: int = 4


@dataclass(frozen=True)
class ClassificationConfig:
    rel20_keywords: tuple[str, ...] = ("Rel-20", "Release 20")
    six_g_keywords: tuple[str, ...] = ("6G", "IMT-2030")
    rel20_work_items: tuple[str, ...] = ()
    six_g_work_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroupRepositoryConfig:
    enabled: bool = False
    base_url: str | None = None
    download_base_url: str | None = None
    start_meeting: str | None = None
    end_meeting: str | None = None


@dataclass(frozen=True)
class Config:
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    source: SourceConfig = field(default_factory=SourceConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    repositories: dict[str, GroupRepositoryConfig] = field(default_factory=dict)


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"configuration section {name!r} must be a mapping")
    return value


def load_config(path: str | Path = "config.yaml") -> Config:
    config_path = Path(path)
    raw: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("configuration root must be a mapping")
        raw = loaded
    scope = _section(raw, "scope")
    paths = _section(raw, "paths")
    source = _section(raw, "source")
    classification = _section(raw, "classification")
    repositories = _section(raw, "repositories")
    parsed_repositories = {
        name.upper(): GroupRepositoryConfig(**value)
        for name, value in repositories.items() if isinstance(value, dict)
    }
    return Config(
        scope=ScopeConfig(**scope),
        paths=PathsConfig(**{k: Path(v) for k, v in paths.items()}),
        source=SourceConfig(**source),
        classification=ClassificationConfig(**{
            k: tuple(v) if isinstance(v, list) else v for k, v in classification.items()
        }),
        repositories=parsed_repositories,
    )
