from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


class ReportWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def write(self, records: list[dict[str, Any]]) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._write_markdown(records)
        self._write_html(records)

    def _write_markdown(self, records: list[dict[str, Any]]) -> None:
        lines = ["# Autoresearch Report", ""]
        if not records:
            lines.append("No trials recorded.")
        else:
            best = self._best_record(records)
            lines.extend(
                [
                    f"- Trials: {len(records)}",
                    f"- Best score: {best.get('score') if best else 'n/a'}",
                    f"- Best trial: {best.get('trial') if best else 'n/a'}",
                    "",
                    "## Trials",
                    "",
                    "| Trial | Score | Accepted | Seconds | Summary |",
                    "| --- | ---: | --- | ---: | --- |",
                ]
            )
            for row in records:
                lines.append(
                    f"| {row.get('trial')} | {row.get('score')} | {row.get('accepted')} | "
                    f"{float(row.get('seconds', 0)):.2f} | {self._md(row.get('summary', ''))} |"
                )
        (self.run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_html(self, records: list[dict[str, Any]]) -> None:
        best = self._best_record(records)
        rows = []
        for row in records:
            rows.append(
                "<tr>"
                f"<td>{escape(str(row.get('trial')))}</td>"
                f"<td>{escape(str(row.get('score')))}</td>"
                f"<td>{'yes' if row.get('accepted') else 'no'}</td>"
                f"<td>{float(row.get('seconds', 0)):.2f}</td>"
                f"<td>{escape(str(row.get('summary', '')))}</td>"
                "</tr>"
            )

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Autoresearch Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #172033; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d8dee8; padding: 8px; text-align: left; }}
    th {{ background: #f6f7f9; }}
    .summary {{ display: flex; gap: 16px; margin: 20px 0; }}
    .box {{ border: 1px solid #d8dee8; border-radius: 8px; padding: 14px; }}
  </style>
</head>
<body>
  <h1>Autoresearch Report</h1>
  <div class="summary">
    <div class="box"><strong>Trials</strong><br>{len(records)}</div>
    <div class="box"><strong>Best score</strong><br>{escape(str(best.get('score') if best else 'n/a'))}</div>
    <div class="box"><strong>Best trial</strong><br>{escape(str(best.get('trial') if best else 'n/a'))}</div>
  </div>
  <table>
    <thead><tr><th>Trial</th><th>Score</th><th>Accepted</th><th>Seconds</th><th>Summary</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""
        (self.run_dir / "report.html").write_text(html, encoding="utf-8")

    @staticmethod
    def _best_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
        accepted = [row for row in records if row.get("accepted") and row.get("score") is not None]
        if not accepted:
            return None
        return accepted[-1]

    @staticmethod
    def _md(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
