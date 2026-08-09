from pathlib import Path


def search_notes(vault_path: str, query: str) -> list[str]:
    """Search for keywords in all .md files in the Obsidian folder."""
    results = []

    vault = Path(vault_path)

    for file_path in vault.rglob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            if (
                query.lower() in file_path.name.lower()
                or query.lower() in content.lower()
            ):
                results.append(f"File: {file_path.name}\nIsi:\n{content[:500]}...\n")
        except OSError:
            continue

    return results
