from pathlib import Path

_notes_cache = {}
_cache_loaded = False

def list_vault_directory(vault_path:str) -> list[str]:
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

def _ensure_cache_loaded(vault_path: str) -> None:
    global _cache_loaded

    if _cache_loaded:
        return

    vault = Path(vault_path)
    EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv"}

    _notes_cache.clear()

    for file_path in vault.rglob("*.md"):
        try:
            if any(part in EXCLUDED_DIRS for part in file_path.parts):
                continue

            rel_path = str(file_path.relative_to(vault))

            content = file_path.read_text(encoding="utf-8", errors="ignore")

            _notes_cache[rel_path] = content
        except OSError:
            continue
    
    _cache_loaded = True

def search_notes(vault_path: str, query: str) -> list[str]:
    """Search for keywords in all cached .md files in the Obsidian folder."""

    _ensure_cache_loaded(vault_path)
    
    results = []
    query_lower = query.lower()

    for rel_path, content in _notes_cache.items():
        filename = Path(rel_path).name

        if query_lower in filename.lower() or query_lower in content.lower():
            preview = content[:500]
            results.append(f"File '{rel_path}'\nContent:\n{preview}")

    return results


def read_note(vault_path: str, filename: str) -> str:
    """Read the full contents of a log file based on its name."""
    resolved_vault = Path(vault_path).resolve()

    matching_files = list(resolved_vault.rglob(filename))

    if not matching_files:
        return f"Error: Notes '{filename}' is not found."

    resolved_file = matching_files[0].resolve()

    if not resolved_file.is_relative_to(resolved_vault):
        return "Error: Access denied. File is outside the vault."

    try:
        return resolved_file.read_text(encoding="utf-8", errors="ignore")
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

        _notes_cache[rel_path_str] = text

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

        if rel_path_str in _notes_cache:
            _notes_cache[rel_path_str] += "\n" + text
        else:
            _notes_cache[rel_path_str] = text
            
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

        import shutil
        shutil.move(str(src_path), str(dest_path))

        _notes_cache.pop(filename, None)

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

        import shutil
        shutil.move(str(src_path), str(dest_path))

        try: 
            content = dest_path.read_text(encoding="utf-8", errors="ignore")
            _notes_cache[filename] = content
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

        import shutil
        shutil.move(str(src_path), str(dest_path))

        # Clear matching cache entries
        prefix = dir_path.rstrip("/") + "/"
        keys_to_remove = [k for k in _notes_cache if k.startswith(prefix) or k == dir_path]
        for k in keys_to_remove:
            _notes_cache.pop(k, None)

        return f"Success: Moved directory '{dir_path}' to trash"
    except OSError as e:
        return f"Error: Failed to move directory '{dir_path}' to trash: {e}"

def get_all_note_paths(vault_path: str) -> list[str]:
    """Retrieve all cached note paths from the vault."""
    _ensure_cache_loaded(vault_path)
    return list(_notes_cache.keys())

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
            

    
