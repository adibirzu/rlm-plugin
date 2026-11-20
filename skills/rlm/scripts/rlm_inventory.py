#!/usr/bin/env python3
"""Build a bounded inventory and a partitioned worklist for an RLM analysis.

The script lists file names and sizes. It reads at most the first kilobyte of
each file to tell text from binary, and it never prints file contents.
Standard output is a compact JSON summary that stays inside --max-output-bytes.
The full list of paths per chunk goes to the --manifest file, which belongs in
the scratch directory and not in the model context.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import stat
import sys
import tempfile
from pathlib import Path

NOISE_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox", "dist",
        "build", "target", "coverage", ".next", ".nuxt", ".cache", ".rlm",
        ".terraform", ".gradle",
    }
)
SKIP_REASONS = (
    "noise_dirs", "symlink_escapes", "symlinks_internal", "binary",
    "unreadable", "depth_limited",
)
SNIFF_BYTES = 1024
DEFAULT_MAX_DEPTH = 64
MAX_DEPTH_LIMIT = 256
BYTES_PER_TOKEN = 4
MIN_OUTPUT_BYTES = 512
TOP_GROUPS = 8
SAMPLE_PATHS = 3

EPILOG = """\
Examples:
  rlm_inventory.py . --manifest .rlm/audit/manifest.json
  rlm_inventory.py services/api --chunk-bytes 120000 --max-files 2000

Exit codes:
  0  inventory written
  2  usage error, or ROOT is not a directory
  3  the manifest file could not be written
"""


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def non_negative_int(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return value


def depth_limit(text: str) -> int:
    value = non_negative_int(text)
    if value > MAX_DEPTH_LIMIT:
        raise argparse.ArgumentTypeError(f"must be at most {MAX_DEPTH_LIMIT}")
    return value


def output_budget(text: str) -> int:
    value = int(text)
    if value < MIN_OUTPUT_BYTES:
        raise argparse.ArgumentTypeError(f"must be at least {MIN_OUTPUT_BYTES}")
    return value


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("root", nargs="?", default=".", help="directory to inventory")
    parser.add_argument("--manifest", type=Path, help="write the full chunk worklist here")
    parser.add_argument("--max-files", type=positive_int, default=5000)
    parser.add_argument("--max-depth", type=depth_limit, default=DEFAULT_MAX_DEPTH,
                        help=f"directory levels below ROOT to enter (default: {DEFAULT_MAX_DEPTH}, "
                             f"at most {MAX_DEPTH_LIMIT})")
    parser.add_argument("--chunk-bytes", type=positive_int, default=200_000,
                        help="byte budget per chunk (default: 200000, about 50k tokens)")
    parser.add_argument("--chunk-files", type=positive_int, default=200,
                        help="file budget per chunk (default: 200)")
    parser.add_argument("--max-output-bytes", type=output_budget, default=4000,
                        help="ceiling for the printed summary (default: 4000)")
    parser.add_argument("--include-noise", action="store_true",
                        help="also list dependency, cache, and build directories")
    return parser.parse_args(argv)


def classify_symlink(path: Path, root: Path, skipped: dict[str, int]) -> None:
    try:
        target = path.resolve(strict=True)
    except (OSError, RuntimeError):
        skipped["unreadable"] += 1
        return
    reason = "symlinks_internal" if target.is_relative_to(root) else "symlink_escapes"
    skipped[reason] += 1


def text_file_size(path: Path) -> int | None:
    """Return the size of a regular text file, or None when it looks binary.

    The file is opened without following a symlink, so an entry swapped for a
    link after it was listed is refused instead of read.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError(f"{path} is not a regular file")
        return None if b"\0" in handle.read(SNIFF_BYTES) else info.st_size


def walk(root: Path, max_files: int, max_depth: int, include_noise: bool):
    """Return ([(relative_path, size)], skipped_counts, truncated)."""
    skipped = dict.fromkeys(SKIP_REASONS, 0)
    files: list[tuple[str, int]] = []

    def unreadable_directory(_error: OSError) -> None:
        skipped["unreadable"] += 1

    for current, dirnames, filenames in os.walk(
        root, followlinks=False, onerror=unreadable_directory
    ):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        entered = []
        for name in sorted(dirnames):
            path = current_path / name
            if path.is_symlink():
                classify_symlink(path, root, skipped)
            elif not include_noise and name in NOISE_DIRS:
                skipped["noise_dirs"] += 1
            elif depth + 1 > max_depth:
                skipped["depth_limited"] += 1
            else:
                entered.append(name)
        dirnames[:] = entered

        for name in sorted(filenames):
            path = current_path / name
            if path.is_symlink():
                classify_symlink(path, root, skipped)
                continue
            try:
                if not path.is_file():
                    raise OSError(f"{path} is not a regular file")
                size = text_file_size(path)
            except OSError:
                skipped["unreadable"] += 1
                continue
            if size is None:
                skipped["binary"] += 1
                continue
            if len(files) >= max_files:
                return files, skipped, True
            files.append((path.relative_to(root).as_posix(), size))
    return files, skipped, False


def estimate_tokens(size: int) -> int:
    return math.ceil(size / BYTES_PER_TOKEN)


def common_directory(paths: list[str]) -> str:
    parents = [path.split("/")[:-1] for path in paths]
    shared = []
    for parts in zip(*parents):
        if len(set(parts)) != 1:
            break
        shared.append(parts[0])
    return "/".join(shared) or "."


def build_chunks(files: list[tuple[str, int]], chunk_bytes: int, chunk_files: int):
    chunks: list[dict] = []
    pending: list[tuple[str, int]] = []

    def flush(oversized: bool = False) -> None:
        if not pending:
            return
        paths = [path for path, _ in pending]
        size = sum(size for _, size in pending)
        chunks.append(
            {
                "id": f"c{len(chunks) + 1:03d}",
                "label": common_directory(paths),
                "files": len(paths),
                "bytes": size,
                "est_tokens": estimate_tokens(size),
                "oversized": oversized,
                "paths": paths,
            }
        )
        pending.clear()

    for path, size in files:
        if size > chunk_bytes:
            flush()
            pending.append((path, size))
            flush(oversized=True)
            continue
        pending_bytes = sum(size for _, size in pending)
        if pending and (pending_bytes + size > chunk_bytes or len(pending) >= chunk_files):
            flush()
        pending.append((path, size))
    flush()
    return chunks


def top_groups(files: list[tuple[str, int]], key_name: str, key) -> list[dict]:
    groups: dict[str, list[int]] = {}
    for path, size in files:
        entry = groups.setdefault(key(path), [0, 0])
        entry[0] += 1
        entry[1] += size
    ranked = sorted(groups.items(), key=lambda item: (-item[1][1], -item[1][0], item[0]))
    return [
        {key_name: name, "files": count, "bytes": size}
        for name, (count, size) in ranked[:TOP_GROUPS]
    ]


def extension_of(path: str) -> str:
    return Path(path).suffix.lower() or "(none)"


def area_of(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else "."


def encode(summary: dict) -> str:
    return json.dumps(summary, separators=(",", ":")) + "\n"


def fit_to_budget(summary: dict, limit: int) -> str:
    """Shrink the summary step by step until it fits the output budget."""
    text = encode(summary)
    if len(text.encode()) <= limit:
        return text

    summary["output_truncated"] = True
    if summary["manifest"] is None:
        summary["hint"] = "rerun with --manifest PATH for the full worklist"

    def drop_samples() -> None:
        for chunk in summary["chunks"]:
            chunk.pop("sample", None)

    def halve_chunks() -> None:
        summary["chunks"] = summary["chunks"][: len(summary["chunks"]) // 2]

    def drop_groups() -> None:
        summary["by_extension"] = []
        summary["by_area"] = []

    steps = [drop_samples]
    steps += [halve_chunks] * max(1, len(summary["chunks"]).bit_length())
    steps += [drop_groups, lambda: summary.pop("hint", None), lambda: summary.pop("skipped")]
    for step in steps:
        step()
        text = encode(summary)
        if len(text.encode()) <= limit:
            return text
    minimal = {
        key: summary[key]
        for key in ("totals", "chunk_count", "truncated", "coverage_complete")
    }
    minimal["output_truncated"] = True
    return encode(minimal)


def addressed_inside(target: Path, root: Path) -> bool:
    """True when some ancestor of the written path is ROOT under any name."""
    for ancestor in target.parents:
        try:
            if ancestor.samefile(root):
                return True
        except OSError:
            continue
    return False


def write_manifest(path: Path, root: Path, chunks: list[dict]) -> None:
    """Write the manifest atomically, without writing through a symlink.

    A manifest addressed inside ROOT must also resolve inside ROOT, so a
    symlinked scratch directory in an untrusted tree cannot redirect the write.
    """
    target = Path(os.path.abspath(path))
    if addressed_inside(target, root) and not target.parent.resolve().is_relative_to(root):
        raise OSError("its directory leaves ROOT through a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"root": str(root), "chunks": chunks}, indent=1) + "\n"
    handle = tempfile.NamedTemporaryFile(
        "w", dir=target.parent, prefix=".manifest-", suffix=".tmp", delete=False
    )
    try:
        with handle:
            handle.write(payload)
        os.replace(handle.name, target)
    except OSError:
        Path(handle.name).unlink(missing_ok=True)
        raise


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {args.root} is not a directory. Pass an existing ROOT.", file=sys.stderr)
        return 2
    root = root.resolve()

    files, skipped, truncated = walk(root, args.max_files, args.max_depth, args.include_noise)
    chunks = build_chunks(files, args.chunk_bytes, args.chunk_files)

    if args.manifest is not None:
        try:
            write_manifest(args.manifest, root, chunks)
        except OSError as error:
            print(f"error: cannot write manifest {args.manifest}: {error}", file=sys.stderr)
            return 3

    total_bytes = sum(size for _, size in files)
    summary = {
        "root": str(root),
        "truncated": truncated,
        "coverage_complete": not (truncated or skipped["unreadable"] or skipped["depth_limited"]),
        "output_truncated": False,
        "totals": {
            "files": len(files),
            "bytes": total_bytes,
            "est_tokens": estimate_tokens(total_bytes),
        },
        "skipped": skipped,
        "by_extension": top_groups(files, "ext", extension_of),
        "by_area": top_groups(files, "area", area_of),
        "chunk_count": len(chunks),
        "chunks": [
            {
                **{key: value for key, value in chunk.items() if key != "paths"},
                "sample": chunk["paths"][:SAMPLE_PATHS],
            }
            for chunk in chunks
        ],
        "manifest": str(args.manifest) if args.manifest is not None else None,
    }
    sys.stdout.flush()
    sys.stdout.buffer.write(fit_to_budget(summary, args.max_output_bytes).encode())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
