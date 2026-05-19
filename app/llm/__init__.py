"""LLM model-call boundary.

This module is responsible only for invoking language models. It accepts
messages, prompts, and optional response schemas as input, and returns
structured JSON output. It does not know about application modes, memory,
or persistence.
"""
