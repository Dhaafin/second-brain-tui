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


def read_note(vault_path: str, filename: str) -> str:
    """Read the full contents of a log file based on its name."""
    vault = Path(vault_path)

    matching_files = list(vault.rglob(filename))

    if not matching_files:
        return f"Error: Notes '{filename}' is not found."

    try:
        return matching_files[0].read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return f"Error: Failed to read '{filename}' due to access rights issues."
