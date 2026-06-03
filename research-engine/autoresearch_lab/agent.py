from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import re
import urllib.error
import urllib.request


@dataclass(frozen=True)
class AgentPatch:
    summary: str
    changed_files: tuple[str, ...]
    raw_response: str


class MistralClient:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        endpoint: str = "https://api.mistral.ai/v1/chat/completions",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.endpoint = endpoint
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, messages: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY is required for Mistral agent mode")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Mistral API error {exc.code}: {body}") from exc

        return data["choices"][0]["message"]["content"]


class CodeAgent:
    def __init__(
        self,
        client: MistralClient,
        files: tuple[str, ...],
        objective: str,
        maximize: bool,
    ) -> None:
        self.client = client
        self.files = files
        self.objective = objective
        self.maximize = maximize

    def propose(self, workspace: Path, trial: int, best_score: float | None) -> AgentPatch:
        prompt = self._build_prompt(workspace, trial, best_score)
        raw = self.client.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        payload = self._parse_json(raw)
        summary = str(payload.get("summary", "Mistral code patch"))
        files = payload.get("files", [])
        if not isinstance(files, list):
            raise ValueError("agent response must contain a files array")

        changed: list[str] = []
        allowed = set(self.files)
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("each file patch must be an object")
            path = str(item.get("path", ""))
            if path not in allowed:
                raise ValueError(f"agent tried to edit a file not listed in agent_files: {path}")
            content = item.get("content")
            if not isinstance(content, str):
                raise ValueError(f"file patch for {path} must include string content")
            destination = self._safe_path(workspace, path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            changed.append(path)

        if not changed:
            raise ValueError("agent returned no changed files")
        return AgentPatch(summary=summary, changed_files=tuple(changed), raw_response=raw)

    def _build_prompt(self, workspace: Path, trial: int, best_score: float | None) -> str:
        direction = "maximize" if self.maximize else "minimize"
        parts = [
            f"Trial: {trial}",
            f"Objective: {self.objective}",
            f"Metric direction: {direction}",
            f"Best score so far: {best_score}",
            "",
            "Allowed editable files:",
            *[f"- {relative}" for relative in self.files],
            "",
            "Forbidden changes:",
            "- Do not edit scripts/score_project.py or any scoring/evaluation script.",
            "- Do not edit tests just to make the score pass.",
            "- Do not edit package manager lock files.",
            "- Do not return any file path outside the allowed editable files list.",
            "- If you want a better score, improve the app UI, data model, components, copy, structure, and completeness.",
            "",
            "Return JSON only, matching this schema:",
            '{"summary":"short rationale","files":[{"path":"relative/file.py","content":"full replacement file content"}]}',
            "",
            "Only edit allowed files. Return full replacement contents, not a diff.",
            "",
        ]

        for relative in self.files:
            path = self._safe_path(workspace, relative)
            if not path.exists():
                parts.append(f"## FILE {relative}\n<missing>\n")
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"## FILE {relative}\n```text\n{content}\n```\n")
        return "\n".join(parts)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("agent response must be a JSON object")
        return data

    @staticmethod
    def _safe_path(root: Path, relative: str) -> Path:
        if not relative or Path(relative).is_absolute():
            raise ValueError(f"unsafe path: {relative}")
        destination = (root / relative).resolve()
        root_resolved = root.resolve()
        if root_resolved != destination and root_resolved not in destination.parents:
            raise ValueError(f"path escapes workspace: {relative}")
        return destination


SYSTEM_PROMPT = """You are an autonomous research coding agent.
Your job is to make one focused code improvement per trial.
You must preserve runnable code, avoid broad rewrites, and optimize the configured metric.
The scoring script is an external evaluator. Never modify the scoring script or any unlisted file.
Return valid JSON only. Do not include markdown prose outside JSON.
"""
