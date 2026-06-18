import os
import shutil
import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional


CATEGORY_MAP = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".raw", ".heic"},
    "Videos": {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".m4v", ".webm", ".mpeg", ".3gp"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".aiff"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".pages", ".tex", ".md", ".epub"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".ods", ".numbers", ".tsv"},
    "Presentations": {".ppt", ".pptx", ".odp", ".key"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz", ".iso", ".dmg"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".sh", ".bash", ".sql", ".json", ".xml", ".yaml", ".yml", ".toml"},
    "Executables": {".exe", ".msi", ".app", ".deb", ".rpm", ".bin", ".apk"},
    "Fonts": {".ttf", ".otf", ".woff", ".woff2", ".eot"},
    "Data": {".db", ".sqlite", ".dbf", ".mdb"},
}


@dataclass
class MoveRecord:
    source: str
    destination: str
    category: str
    timestamp: str
    file_hash: str


@dataclass
class OrganizerReport:
    source_directory: str
    timestamp: str
    moved: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def setup_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("file_organizer")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def compute_hash(filepath: Path, chunk_size: int = 65536) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_category(extension: str) -> str:
    ext = extension.lower()
    for category, extensions in CATEGORY_MAP.items():
        if ext in extensions:
            return category
    return "Miscellaneous"


def resolve_collision(destination: Path) -> Path:
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    candidate = destination
    while candidate.exists():
        candidate = parent / f"{stem}_({counter}){suffix}"
        counter += 1
    return candidate


def organize_directory(
    source_dir: str,
    target_dir: Optional[str] = None,
    dry_run: bool = False,
    deduplicate: bool = True,
) -> OrganizerReport:
    source = Path(source_dir).resolve()
    target = Path(target_dir).resolve() if target_dir else source

    if not source.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source}")

    log_path = target / f"organizer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(log_path if not dry_run else Path(os.devnull))
    report = OrganizerReport(
        source_directory=str(source),
        timestamp=datetime.now().isoformat(),
    )

    seen_hashes: dict[str, Path] = {}
    category_counts: dict[str, int] = defaultdict(int)

    files = [f for f in source.rglob("*") if f.is_file() and not f.name.startswith(".")]
    logger.info(f"Discovered {len(files)} file(s) in '{source}'")

    for filepath in files:
        if filepath.parent.resolve() == target.resolve() and str(filepath).endswith(".log"):
            continue

        try:
            file_hash = compute_hash(filepath)
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot read '{filepath.name}': {e}")
            report.errors.append({"file": str(filepath), "reason": str(e)})
            continue

        if deduplicate and file_hash in seen_hashes:
            original = seen_hashes[file_hash]
            logger.warning(f"Duplicate detected: '{filepath.name}' matches '{original.name}' — skipping")
            report.duplicates.append({"file": str(filepath), "original": str(original)})
            continue

        seen_hashes[file_hash] = filepath
        category = resolve_category(filepath.suffix)
        dest_dir = target / category
        dest_path = dest_dir / filepath.name

        if dest_path.exists():
            dest_path = resolve_collision(dest_path)

        record = MoveRecord(
            source=str(filepath),
            destination=str(dest_path),
            category=category,
            timestamp=datetime.now().isoformat(),
            file_hash=file_hash,
        )

        if dry_run:
            logger.info(f"[DRY RUN] Would move '{filepath.name}' → {category}/")
            report.moved.append(asdict(record))
        else:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(filepath), str(dest_path))
                logger.info(f"Moved '{filepath.name}' → {category}/")
                report.moved.append(asdict(record))
                category_counts[category] += 1
            except (OSError, shutil.Error) as e:
                logger.error(f"Failed to move '{filepath.name}': {e}")
                report.errors.append({"file": str(filepath), "reason": str(e)})

    report.stats = {
        "total_discovered": len(files),
        "total_moved": len(report.moved),
        "total_skipped": len(report.skipped),
        "total_duplicates": len(report.duplicates),
        "total_errors": len(report.errors),
        "by_category": dict(category_counts),
    }

    if not dry_run:
        report_path = target / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(asdict(report) if hasattr(report, "__dataclass_fields__") else report.__dict__, f, indent=2, default=str)
        logger.info(f"Report saved → {report_path}")

    return report


def print_summary(report: OrganizerReport) -> None:
    stats = report.stats
    width = 52
    border = "─" * width

    print(f"\n┌{border}┐")
    print(f"│{'  FILE ORGANIZER — SUMMARY':^{width}}│")
    print(f"├{border}┤")
    print(f"│  {'Source':<22} {report.source_directory[-26:]:>26}  │")
    print(f"│  {'Timestamp':<22} {report.timestamp[:19]:>26}  │")
    print(f"├{border}┤")
    print(f"│  {'Discovered':<30} {stats.get('total_discovered', 0):>18}  │")
    print(f"│  {'Moved':<30} {stats.get('total_moved', 0):>18}  │")
    print(f"│  {'Duplicates Skipped':<30} {stats.get('total_duplicates', 0):>18}  │")
    print(f"│  {'Errors':<30} {stats.get('total_errors', 0):>18}  │")

    by_cat = stats.get("by_category", {})
    if by_cat:
        print(f"├{border}┤")
        print(f"│{'  BY CATEGORY':^{width}}│")
        print(f"├{border}┤")
        for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"│  {cat:<30} {count:>18}  │")

    print(f"└{border}┘\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Automatically organize files into categorized folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", help="Directory to organize")
    parser.add_argument("--target", default=None, help="Target directory (defaults to source)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without moving files")
    parser.add_argument("--no-dedup", action="store_true", help="Disable duplicate detection")

    args = parser.parse_args()

    report = organize_directory(
        source_dir=args.source,
        target_dir=args.target,
        dry_run=args.dry_run,
        deduplicate=not args.no_dedup,
    )
    print_summary(report)
