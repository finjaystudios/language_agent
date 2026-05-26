import pytest
from app.infrastructure.llm import schema_loader


def test_load_schema_returns_schema_mapping_from_yaml(tmp_path, monkeypatch):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "lite.yaml").write_text(
        "type: object\nrequired:\n  - response\n", encoding="utf-8"
    )
    monkeypatch.setattr(schema_loader, "SCHEMAS_DIR", schemas_dir)

    result = schema_loader.load_schema("lite")

    assert result["required"] == ["response"]


def test_load_schema_raises_for_missing_schema_file(tmp_path, monkeypatch):
    monkeypatch.setattr(schema_loader, "SCHEMAS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError) as error:
        schema_loader.load_schema("missing")

    assert "Schema file not found" in str(error.value)


def test_load_schema_raises_when_yaml_is_not_mapping(tmp_path, monkeypatch):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "bad.yaml").write_text("- response\n", encoding="utf-8")
    monkeypatch.setattr(schema_loader, "SCHEMAS_DIR", schemas_dir)

    with pytest.raises(ValueError) as error:
        schema_loader.load_schema("bad")

    assert "YAML mapping" in str(error.value)
