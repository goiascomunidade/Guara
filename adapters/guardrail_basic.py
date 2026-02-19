from __future__ import annotations

import re


class BasicGuardrail:
    """Minimal guardrail for blocking obvious unsafe or forbidden content."""

    def __init__(
        self,
        *,
        blocked_input_patterns: list[str] | None = None,
        blocked_output_patterns: list[str] | None = None,
        max_output_chars: int = 2_000,
    ) -> None:
        input_patterns = blocked_input_patterns or [
            r"ignore previous instructions",
            r"\brm\s+-rf\b",
            r"jailbreak",
        ]
        output_patterns = blocked_output_patterns or [
            r"api[_ -]?key",
            r"secret",
        ]
        self._input_rules = [re.compile(pattern, re.IGNORECASE) for pattern in input_patterns]
        self._output_rules = [re.compile(pattern, re.IGNORECASE) for pattern in output_patterns]
        self._max_output_chars = max_output_chars

    async def validate_input(self, content: str) -> tuple[bool, str | None]:
        for rule in self._input_rules:
            if rule.search(content):
                return False, "Entrada bloqueada por política de segurança."
        return True, None

    async def validate_output(self, content: str) -> tuple[bool, str | None]:
        if len(content) > self._max_output_chars:
            return False, "Saída excede limite de segurança."
        for rule in self._output_rules:
            if rule.search(content):
                return False, "Saída bloqueada por política de segurança."
        return True, None

