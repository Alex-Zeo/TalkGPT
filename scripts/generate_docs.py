#!/usr/bin/env python3
"""
Aggregate module docs (AGENTS_*.md) into AGENTS.md between markers.
"""

from pathlib import Path

START = "<!-- START:GENERATED -->"
END = "<!-- END:GENERATED -->"


def collect_module_docs(root: Path) -> str:
    parts = []
    for name in [
        "AGENTS_core.md",
        "AGENTS_analytics.md",
        "AGENTS_utils.md",
        "AGENTS_cli.md",
        "AGENTS_mcp.md",
        "AGENTS_workers.md",
    ]:
        p = root / name
        if p.exists():
            parts.append(f"\n\n<!-- {name} -->\n\n" + p.read_text(encoding="utf-8"))
    return "\n".join(parts).strip() + "\n"


def update_agents_md(root: Path, generated: str):
    agents_md = root / "AGENTS.md"
    content = agents_md.read_text(encoding="utf-8") if agents_md.exists() else "# TalkGPT - AGENTS\n\n"

    if START in content and END in content:
        prefix = content.split(START)[0]
        suffix = content.split(END)[-1]
        new_content = f"{prefix}{START}\n{generated}\n{END}{suffix}"
    else:
        # Append a generated section at the end
        if not content.endswith("\n"):
            content += "\n"
        new_content = content + f"\n{START}\n{generated}{END}\n"

    agents_md.write_text(new_content, encoding="utf-8")


def main():
    root = Path(__file__).resolve().parent.parent
    generated = collect_module_docs(root)
    update_agents_md(root, generated)
    print("Updated AGENTS.md with generated module docs section.")


if __name__ == "__main__":
    main()


