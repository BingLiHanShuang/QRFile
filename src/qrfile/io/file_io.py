"""File I/O and source file listing"""

from pathlib import Path
from qrfile.errors import FileLimitError, EncodeError

# Source code / text file extensions
_SOURCE_EXTENSIONS = {
    ".txt", ".md", ".rst", ".log", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".properties",
    ".py", ".pyw", ".c", ".cpp", ".h", ".hpp", ".cc", ".cxx", ".cs",
    ".java", ".kt", ".kts", ".scala", ".groovy",
    ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1",
    ".go", ".rs", ".rb", ".php", ".swift", ".lua", ".r", ".pl",
    ".sql", ".graphql", ".proto",
    ".vue", ".svelte", ".astro",
}

# Full filenames without extensions (dotfiles, Dockerfile, etc.)
_FULLNAME_WHITELIST = {
    ".gitignore", ".gitattributes", ".editorconfig",
    ".env", ".env.example", ".env.local", ".env.production", ".env.development",
    "dockerfile", "makefile", "cmakelists.txt",
    "license", "changelog", "readme",
}

# Binary file extensions to exclude
_BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".obj", ".o", ".a", ".lib",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav", ".flac",
    ".ttf", ".otf", ".woff", ".woff2",
    ".pyc", ".pyo", ".class", ".jar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".db", ".sqlite", ".sqlite3",
}

# Directories to skip during recursive scan
_SKIP_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", ".pytest_cache",
    "node_modules", ".venv", "venv", ".tox", ".eggs",
    ".mypy_cache", ".ruff_cache", ".idea", ".vscode",
    "dist", "build", ".next", ".nuxt",
}


def read_file_bytes(path: Path) -> bytes:
    """Read file contents in binary mode"""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        raise EncodeError(f"Failed to read file: {path} - {e}") from e


def write_file_bytes(path: Path, data: bytes) -> None:
    """Write bytes to file, creating parent directories as needed"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def list_source_files(directory: Path, max_files: int) -> list[Path]:
    """Recursively list all convertible text/code files in a directory

    Supports extensions: .py .c .cpp .js .ts .html .css .sh .go .rs .java ...
    Skips binary files (.exe .dll .png .zip ...) and VCS/build directories.

    Args:
        directory: Directory to scan
        max_files: Maximum number of files (0 = unlimited)

    Returns:
        List of file paths sorted by path

    Raises:
        NotADirectoryError: Path is not a directory
        FileLimitError: File count exceeds max_files
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    files: list[Path] = []
    for p in sorted(directory.rglob("*")):
        if any(skip in p.parts for skip in _SKIP_DIRS):
            continue
        if not p.is_file():
            continue

        if p.name.lower() in _FULLNAME_WHITELIST:
            files.append(p)
            continue

        if not p.suffix:
            continue

        if p.suffix.lower() in _BINARY_EXTENSIONS:
            continue

        if p.suffix.lower() in _SOURCE_EXTENSIONS:
            files.append(p)

    if max_files > 0 and len(files) > max_files:
        raise FileLimitError(
            f"Found {len(files)} convertible files, exceeds limit of {max_files}. "
            f"Use --max-files 0 to remove limit."
        )

    return files
