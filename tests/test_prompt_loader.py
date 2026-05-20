import pytest
from app.llm import prompt_loader


def test_load_prompt_returns_prompt_text_from_yaml(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "greeting.yaml").write_text(
        "prompt: |\n  Hello {name}\n", encoding="utf-8"
    )
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", prompts_dir)

    result = prompt_loader.load_prompt("greeting")

    assert result == "Hello {name}\n"


def test_load_prompt_raises_for_missing_prompt_file(tmp_path, monkeypatch):
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError) as error:
        prompt_loader.load_prompt("missing")

    assert "Prompt file not found" in str(error.value)


def test_load_prompt_raises_when_yaml_is_not_mapping(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "bad.yaml").write_text("- prompt\n", encoding="utf-8")
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", prompts_dir)

    with pytest.raises(ValueError) as error:
        prompt_loader.load_prompt("bad")

    assert "YAML mapping" in str(error.value)


def test_load_prompt_raises_when_prompt_value_is_not_string(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "bad.yaml").write_text("prompt: 123\n", encoding="utf-8")
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", prompts_dir)

    with pytest.raises(ValueError) as error:
        prompt_loader.load_prompt("bad")

    assert "string `prompt` value" in str(error.value)
