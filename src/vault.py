import shutil
from pathlib import Path

# --- Two-tier cache: paths load fast, content loads lazy on-demand ---
_note_paths_cache: list[str] = []
_folders_cache: list[str] = []
_note_content_cache: dict[str, str] = {}
_paths_loaded = False

# Keep legacy alias so external reads from _notes_cache still work
_notes_cache = _note_content_cache


def _ensure_paths_loaded(vault_path: str) -> None:
    """Load only file paths and folder paths — no file content read."""
    global _paths_loaded

    if _paths_loaded:
        return

    vault = Path(vault_path)
    EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}

    _note_paths_cache.clear()
    _folders_cache.clear()

    for p in vault.rglob("*"):
        try:
            if any(part in EXCLUDED_DIRS for part in p.parts):
                continue

            if p.is_dir():
                rel_path = str(p.relative_to(vault)).replace("\\", "/")
                if rel_path:
                    _folders_cache.append(rel_path)
            elif p.is_file() and p.suffix == ".md":
                rel_path = str(p.relative_to(vault)).replace("\\", "/")
                _note_paths_cache.append(rel_path)
        except OSError:
            continue

    _folders_cache.sort()
    _note_paths_cache.sort()
    _paths_loaded = True


def _get_note_content(vault_path: str, rel_path: str) -> str | None:
    """Lazy-load a single note's content into cache on demand."""
    if rel_path in _note_content_cache:
        return _note_content_cache[rel_path]

    full_path = Path(vault_path) / rel_path
    try:
        if full_path.is_file():
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            _note_content_cache[rel_path] = content
            return content
    except OSError:
        pass
    return None


# Legacy compat: old code calls _ensure_cache_loaded
def _ensure_cache_loaded(vault_path: str) -> None:
    _ensure_paths_loaded(vault_path)


def list_vault_directory(vault_path: str) -> list[str]:
    resolved_vault = Path(vault_path).resolve()
    EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}
    dirs = []

    for p in resolved_vault.rglob("*"):
        if p.is_dir():
            if any(part in EXCLUDED_DIRS for part in p.parts):
                continue
            rel_path = p.relative_to(resolved_vault)

            if len(rel_path.parts) <= 2:
                clean_path = str(rel_path).replace("\\", "/")
                dirs.append(clean_path)

    return sorted(dirs)


def get_all_folder_paths(vault_path: str) -> list[str]:
    """Retrieve all cached folder paths from the vault."""
    _ensure_paths_loaded(vault_path)
    return _folders_cache


def add_folder_to_cache(vault_path: str, rel_path: str) -> None:
    """Expose adding a folder to the in-memory cache directly."""
    _ensure_paths_loaded(vault_path)
    clean_path = rel_path.replace("\\", "/")
    if clean_path and clean_path not in _folders_cache:
        _folders_cache.append(clean_path)
        _folders_cache.sort()


def search_notes(vault_path: str, query: str) -> list[str]:
    """Search for keywords in all cached .md files in the Obsidian folder."""
    _ensure_paths_loaded(vault_path)

    results = []
    query_lower = query.lower()

    for rel_path in _note_paths_cache:
        filename = Path(rel_path).name

        # Check filename match first (no content read needed)
        if query_lower in filename.lower():
            content = _get_note_content(vault_path, rel_path)
            preview = (content or "")[:500]
            results.append(f"File '{rel_path}'\nContent:\n{preview}")
            continue

        # Only load content if filename didn't match
        content = _get_note_content(vault_path, rel_path)
        if content and query_lower in content.lower():
            preview = content[:500]
            results.append(f"File '{rel_path}'\nContent:\n{preview}")

    return results


def read_note(vault_path: str, filename: str) -> str:
    """Read the full contents of a log file based on its name or relative path."""
    resolved_vault = Path(vault_path).resolve()

    # Try direct relative path lookup first to avoid duplicate filename rglob issues
    direct_file = (resolved_vault / filename).resolve()
    if direct_file.is_file() and direct_file.is_relative_to(resolved_vault):
        matching_files = [direct_file]
    else:
        matching_files = list(resolved_vault.rglob(filename))

    if not matching_files:
        return f"Error: Notes '{filename}' is not found."

    resolved_file = matching_files[0].resolve()

    if not resolved_file.is_relative_to(resolved_vault):
        return "Error: Access denied. File is outside the vault."

    try:
        content = resolved_file.read_text(encoding="utf-8", errors="ignore")
        # Update content cache
        rel_path = str(resolved_file.relative_to(resolved_vault)).replace("\\", "/")
        _note_content_cache[rel_path] = content
        return content
    except OSError:
        return f"Error: Failed to read '{filename}' due to access rights issues."

def write_note(base_dir_str : str, rel_path_str: str, text: str) -> str:
    base_dir = Path(base_dir_str).resolve()

    target_file= (base_dir / rel_path_str).resolve()

    if not target_file.is_relative_to(base_dir):
        return "Error: Access denied. Target path is outside the sandbox"

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        target_file.write_text(text, encoding="utf-8")

        # Normalize path representation
        normalized_rel_path = rel_path_str.replace("\\", "/")
        _note_content_cache[normalized_rel_path] = text

        # Add to paths cache if not present
        if normalized_rel_path not in _note_paths_cache:
            _note_paths_cache.append(normalized_rel_path)
            _note_paths_cache.sort()

        # Update folders cache
        parent_parts = Path(normalized_rel_path).parent.parts
        if parent_parts:
            for i in range(1, len(parent_parts) + 1):
                parent_path = "/".join(parent_parts[:i])
                if parent_path and parent_path not in _folders_cache:
                    _folders_cache.append(parent_path)
            _folders_cache.sort()

        return f"Success: Note '{rel_path_str}' has been saved."
    except OSError:
        return f"Error: Failed to write '{rel_path_str}' due to access issues."

def append_note(base_dir_str: str, rel_path_str:str, text:str) -> str:
    base_dir =Path(base_dir_str).resolve()
    target_file = (base_dir/rel_path_str).resolve()

    if not target_file.is_relative_to(base_dir):
        return "Error: Access denied. Target path is outside the sandbox"

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)

        with open(target_file, "a", encoding="utf-8") as f:
            f.write ("\n" + text)

        normalized = rel_path_str.replace("\\", "/")
        if normalized in _note_content_cache:
            _note_content_cache[normalized] += "\n" + text
        else:
            _note_content_cache[normalized] = text

        # Add to paths cache if not present
        if normalized not in _note_paths_cache:
            _note_paths_cache.append(normalized)
            _note_paths_cache.sort()

        return f"Success: Content Appended to '{rel_path_str}'"
    except OSError:
        return f"Error: Failed to append to '{rel_path_str}' due to access"
         
def delete_to_trash(vault_path:str, filename:str) -> str:
    resolved_vault = Path(vault_path).resolve()
    src_path = (resolved_vault / filename).resolve()
    dest_path = (resolved_vault / ".trash" / filename).resolve()

    if not src_path.is_relative_to(resolved_vault) or src_path == resolved_vault:
        return "Error : Access denied. Cannot delete files outside of the vault"

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src_path), str(dest_path))

        normalized = filename.replace("\\", "/")
        _note_content_cache.pop(normalized, None)
        if normalized in _note_paths_cache:
            _note_paths_cache.remove(normalized)

        return f"Success: Moved '{filename}' to trash"
    except OSError:
        return f"Error: failed to move '{filename}' to trash due to access issues"

def restore_from_trash(vault_path:str, filename:str) -> str:
    resolved_vault = Path(vault_path).resolve()
    src_path = (resolved_vault / ".trash" / filename).resolve()
    dest_path = (resolved_vault / filename).resolve()

    if not src_path.exists():
        return f"Error: '{filename}' not found in trash."
    
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src_path), str(dest_path))

        try: 
            content = dest_path.read_text(encoding="utf-8", errors="ignore")
            normalized = filename.replace("\\", "/")
            _note_content_cache[normalized] = content
            if normalized not in _note_paths_cache:
                _note_paths_cache.append(normalized)
                _note_paths_cache.sort()
        except OSError:
            pass

        return f"Success: Restored '{filename}' from trash."
    except OSError:
        return f"Error: Failed to restore '{filename}' due to access issues."

def delete_directory_to_trash(vault_path: str, dir_path: str) -> str:
    resolved_vault = Path(vault_path).resolve()
    src_path = (resolved_vault / dir_path).resolve()
    dest_path = (resolved_vault / ".trash" / dir_path).resolve()

    if not src_path.is_relative_to(resolved_vault) or src_path == resolved_vault:
        return "Error: Access denied. Cannot delete directory outside or equal to vault root"

    if not src_path.exists():
        return f"Error: Directory '{dir_path}' not found."

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src_path), str(dest_path))

        # Clear matching cache entries
        prefix = dir_path.rstrip("/") + "/"
        keys_to_remove = [k for k in _note_content_cache if k.startswith(prefix) or k == dir_path]
        for k in keys_to_remove:
            _note_content_cache.pop(k, None)

        # Clear matching paths cache entries
        global _note_paths_cache
        _note_paths_cache[:] = [p for p in _note_paths_cache if not (p.startswith(prefix) or p == dir_path)]

        # Clear matching folders cache entries
        global _folders_cache
        _folders_cache = [f for f in _folders_cache if not (f.startswith(prefix) or f == dir_path)]

        return f"Success: Moved directory '{dir_path}' to trash"
    except OSError as e:
        return f"Error: Failed to move directory '{dir_path}' to trash: {e}"

def get_all_note_paths(vault_path: str) -> list[str]:
    """Retrieve all cached note paths from the vault."""
    _ensure_paths_loaded(vault_path)
    return list(_note_paths_cache)

def generate_vault_index(vault_path: str) -> str:
    """Scan all markdown files in the vault and generate a structured index map."""
    resolved_vault = Path(vault_path).resolve()
    EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}
    
    folders_map = {}
    
    for file_path in resolved_vault.rglob("*.md"):
        if any(part in EXCLUDED_DIRS for part in file_path.parts):
            continue
        if file_path.name == "Agent Memory.md":
            continue
            
        try:
            rel_path = file_path.relative_to(resolved_vault)
            parts = rel_path.parts
            
            # Group by folder
            folder_group = "/".join(parts[:-1]) if len(parts) > 1 else "/"
            
            # Extract first heading
            title = file_path.stem
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                        
            if folder_group not in folders_map:
                folders_map[folder_group] = []
                
            folders_map[folder_group].append({
                "title": title,
                "path": str(rel_path).replace("\\", "/")
            })
        except OSError:
            continue
            
    md_lines = ["\n## 🗺️ Vault Knowledge Map\n"]
    for folder in sorted(folders_map.keys()):
        md_lines.append(f"\n### 📁 {folder}")
        for note in sorted(folders_map[folder], key=lambda x: x["path"]):
            md_lines.append(f"- **{note['title']}** (`{note['path']}`)")
            
    return "\n".join(md_lines)

def update_vault_index_in_memory(vault_path: str) -> None:
    """Updates only the Vault Knowledge Map section in Agent Memory.md, keeping user edits intact."""
    resolved_vault = Path(vault_path).resolve()
    memory_file = resolved_vault / "Agent Memory.md"
    if not memory_file.exists():
        return
        
    try:
        content = memory_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
        
    new_map = generate_vault_index(vault_path)
    map_block = f"<!-- MAP_START -->\n{new_map}\n<!-- MAP_END -->"
    
    if "<!-- MAP_START -->" in content:
        parts = content.split("<!-- MAP_START -->")
        header = parts[0]
        footer = ""
        if "<!-- MAP_END -->" in parts[1]:
            subparts = parts[1].split("<!-- MAP_END -->")
            footer = subparts[1]
        new_content = header + map_block + footer
    else:
        new_content = content.rstrip() + "\n\n" + map_block
        
    try:
        memory_file.write_text(new_content, encoding="utf-8")
    except OSError:
        pass
