from ran2wiki.config import load_config


def test_defaults_without_file(tmp_path) -> None:
    config = load_config(tmp_path / "missing.yaml")
    assert config.scope.start_meeting == "125"
    assert config.scope.include_6g is True

