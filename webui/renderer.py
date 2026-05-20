from __future__ import annotations

from typing import Any


def render_chat_response(result: dict[str, Any]) -> str:
    data = result.get("data")
    if isinstance(data, dict):
        mode = data.get("mode") or result.get("mode")
        if mode == "definition":
            return render_definition(data, result)
        if mode == "translation":
            return render_translation(data, result)
        if mode == "learning":
            return render_learning(data, result)

    response = result.get("response")
    if isinstance(response, str) and response.strip():
        return response

    return ""


def render_definition(data: dict[str, Any], result: dict[str, Any]) -> str:
    lines: list[str] = []

    term = string_value(data.get("term"))
    part_of_speech = string_value(data.get("part_of_speech"))
    language = string_value(data.get("language"))
    pronunciation = string_value(data.get("pronunciation"))
    meaning = string_value(data.get("meaning"))
    response = string_value(data.get("response") or result.get("response"))

    title = term or "Definition"
    if part_of_speech:
        title = f"{title} ({part_of_speech})"
    lines.append(f"**{title}**")

    details = []
    if language and language != "unknown":
        details.append(f"Language: {language}")
    if pronunciation:
        details.append(f"Pronunciation: {pronunciation}")
    if details:
        lines.append(" | ".join(details))

    if meaning:
        lines.extend(["", meaning])
    elif response:
        lines.extend(["", response])

    append_list(lines, "Examples", data.get("examples"))
    append_list(lines, "Synonyms", data.get("synonyms"), inline=True)
    append_list(lines, "Antonyms", data.get("antonyms"), inline=True)

    etymology = string_value(data.get("etymology"))
    if etymology:
        lines.extend(["", f"**Etymology:** {etymology}"])

    if response and response not in lines and response != meaning:
        lines.extend(["", response])

    return "\n".join(lines).strip()


def render_translation(data: dict[str, Any], result: dict[str, Any]) -> str:
    translated_text = string_value(data.get("translated_text"))
    response = string_value(data.get("response") or result.get("response"))
    source_language = string_value(data.get("source_language"))
    target_language = string_value(data.get("target_language"))

    lines = []
    if translated_text:
        lines.append(translated_text)
    elif response:
        lines.append(response)

    if source_language or target_language:
        lines.extend(
            [
                "",
                f"`{source_language or 'unknown'}` -> `{target_language or 'unknown'}`",
            ]
        )

    return "\n".join(lines).strip()


def render_learning(data: dict[str, Any], result: dict[str, Any]) -> str:
    response = string_value(data.get("response") or result.get("response"))
    lines = [response] if response else []

    teaching_point = string_value(data.get("teaching_point"))
    if teaching_point and teaching_point != response:
        lines.extend(["", f"**Teaching point:** {teaching_point}"])

    append_list(lines, "Examples", data.get("examples"))
    append_list(lines, "Corrections", data.get("corrections"))
    append_list(lines, "Exercises", data.get("exercises"))

    next_step = string_value(data.get("next_suggested_step"))
    if next_step:
        lines.extend(["", f"**Next step:** {next_step}"])

    return "\n".join(lines).strip()


def append_list(
    lines: list[str],
    title: str,
    values: object,
    *,
    inline: bool = False,
) -> None:
    if not isinstance(values, list):
        return

    items = [string_value(value) for value in values]
    items = [item for item in items if item]
    if not items:
        return

    if inline:
        lines.extend(["", f"**{title}:** {', '.join(items)}"])
        return

    lines.extend(["", f"**{title}:**"])
    lines.extend(f"- {item}" for item in items)


def string_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""
