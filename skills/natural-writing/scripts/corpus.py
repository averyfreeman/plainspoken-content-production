#!/usr/bin/env python3
"""Local, stdlib-only source inventory and evidence-backed voice profiles.

This helper does not fetch URLs, call a model, or infer anyone's voice. The
agent reads and analyzes sources using its host tools, then records coverage.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile

DEFAULT_LIBRARY = Path.home() / ".natural-writing" / "profiles"
TEXT_TYPES = {".txt", ".md", ".rst", ".html", ".htm"}
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}
ROLES = ("voice", "reference", "notes")
MAX_SOURCE_BYTES = 16 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li", "article"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def source_text(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("file unavailable or is a symlink")
    if path.suffix.lower() not in TEXT_TYPES or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("export as a smaller UTF-8 text file using the host's document tools")
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if "\x00" in text:
        raise ValueError("binary content needs a text export")
    if path.suffix.lower() in {".html", ".htm"}:
        parser = PlainHTML()
        parser.feed(text)
        text = "".join(parser.parts)
    return text


def atomic_write(path, text):
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(text)
        temp.replace(path)
    finally:
        if temp and temp.exists():
            temp.unlink()


class Library:
    def __init__(self, root, subject):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", subject):
            raise ValueError("subject must be a lowercase slug, 1-64 letters, digits or hyphens")
        self.root = Path(root).expanduser().resolve()
        self.subject = subject
        self.folder = self.root / subject
        if self.folder.is_symlink():
            raise ValueError("a subject folder cannot be a symlink to another library entry")
        self.index_path = self.folder / "sources.jsonl"
        self.meta_path = self.folder / "subject.json"

    @contextmanager
    def locked(self):
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = self.folder / ".lock"
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ValueError("this subject is being updated; retry after that operation completes") from None
        try:
            os.close(fd)
            yield
        finally:
            lock.unlink()

    def metadata(self):
        return json.loads(self.meta_path.read_text()) if self.meta_path.exists() else {
            "schema_version": 1, "subject": self.subject, "name": self.subject,
            "profile_stale": True, "profile_sources": {},
        }

    def entries(self):
        if not self.index_path.exists():
            return {}
        rows = [json.loads(line) for line in self.index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return {row["id"]: row for row in rows}

    def save(self, entries, meta):
        atomic_write(self.index_path, "".join(json.dumps(entries[k], ensure_ascii=False, sort_keys=True) + "\n" for k in sorted(entries)))
        atomic_write(self.meta_path, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")

    def inventory(self, inputs, manifests=(), role="voice", author="", authorship="unknown", name=None):
        with self.locked():
            old = self.entries()
            entries = dict(old)
            meta = self.metadata()
            if name and meta["name"] not in {self.subject, name}:
                raise ValueError("subject already belongs to a different name; use a different slug")
            if name:
                meta["name"] = name
            supplied = []
            for raw in inputs:
                path = Path(raw).expanduser().absolute()
                if path.is_dir() and not path.is_symlink():
                    def inaccessible(error):
                        supplied.append({"locator": str(error.filename), "role": role, "access_note": "Directory unavailable during inventory"})
                    for directory, dirs, files in os.walk(path, followlinks=False, onerror=inaccessible):
                        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not Path(directory, d).is_symlink() and not Path(directory, d).resolve().is_relative_to(self.root))
                        for file in sorted(files):
                            item = Path(directory, file)
                            if not item.resolve().is_relative_to(self.root):
                                supplied.append({"locator": str(item), "text_path": str(item), "role": role, "author": author, "authorship": authorship})
                else:
                    supplied.append({"locator": str(path), "text_path": str(path), "role": role, "author": author, "authorship": authorship})
            for manifest in manifests:
                manifest_path = Path(manifest).expanduser().resolve()
                for line in manifest_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("manifest records must be objects")
                    for field in ("locator", "text_path", "title", "author", "published_at", "medium", "access_note"):
                        if field in item and item[field] is not None and not isinstance(item[field], str):
                            raise ValueError(f"manifest {field} must be text")
                    if item.get("medium") is None:
                        item["medium"] = "unspecified"
                    if item.get("text_path"):
                        item["text_path"] = str((manifest_path.parent / Path(item["text_path"]).expanduser()).absolute())
                    supplied.append(item)
            # Refresh known local/export paths, including items removed from a folder.
            by_key = {(e["role"], e["locator"]): e for e in entries.values()}
            for item in supplied:
                if not isinstance(item, dict) or not isinstance(item.get("locator"), str) or not item["locator"].strip():
                    raise ValueError("each manifest item needs a nonempty locator")
                item_role = item.get("role", role)
                if item_role not in ROLES or item.get("authorship", "unknown") not in {"confirmed", "unknown", "ai"}:
                    raise ValueError("invalid source role or authorship")
                key = item_role, item["locator"]
                by_key[key] = {**by_key.get(key, {}), **item, "role": item_role}
            for (item_role, locator), item in by_key.items():
                sid = hashlib.sha256((item_role + "\0" + locator).encode()).hexdigest()[:16]
                previous = old.get(sid, {})
                row = {"id": sid, "locator": locator, "role": item_role,
                       "title": item.get("title") or Path(locator).name,
                       "author": item.get("author", ""), "authorship": item.get("authorship", "unknown"),
                       "published_at": item.get("published_at"), "medium": item.get("medium", "unspecified"),
                       "text_path": item.get("text_path"), "checked_at": now(),
                       "fingerprint": None, "words": 0, "access": "unavailable"}
                text_path = row["text_path"]
                if text_path:
                    try:
                        text = source_text(text_path)
                        row.update(access="available", fingerprint=hashlib.sha256(text.encode()).hexdigest(), words=len(text.split()))
                        row["modified_at"] = datetime.fromtimestamp(Path(text_path).stat().st_mtime, timezone.utc).isoformat()
                    except (OSError, UnicodeError, ValueError) as exc:
                        row["access"] = "needs_export" if Path(text_path).exists() else "unavailable"
                        row["access_note"] = str(exc)
                else:
                    row["access_note"] = item.get("access_note", "Fetch with the host's tools and supply a text export; this helper does not access the network.")
                stable = all(row.get(k) == previous.get(k) for k in ("fingerprint", "author", "authorship", "published_at", "medium", "access"))
                row["read_status"] = previous.get("read_status", "indexed") if stable else "indexed"
                if stable and previous.get("reading_note"):
                    row["reading_note"] = previous["reading_note"]
                if not stable:
                    meta["profile_stale"] = True
                entries[sid] = row
            seen = {}
            # Prefer confirmed writing as the canonical copy. Otherwise an
            # unknown repost could hide the only usable sample from sampling.
            for sid in sorted(entries, key=lambda k: (entries[k]["authorship"] != "confirmed", k)):
                row = entries[sid]
                key = row["role"], row.get("fingerprint")
                row.pop("duplicate_of", None)
                if row.get("fingerprint"):
                    if key in seen:
                        row["duplicate_of"] = seen[key]
                    else:
                        seen[key] = sid
            meta["updated_at"] = now()
            self.save(entries, meta)
        return self.status()

    def mark_read(self, sid, level, note=""):
        with self.locked():
            entries = self.entries()
            if sid not in entries or entries[sid]["access"] != "available":
                raise ValueError("source is unavailable; fetch or export it first")
            entries[sid].update(read_status=level, reading_note=note)
            self.save(entries, self.metadata())

    def read(self, sid, start=1, lines=120):
        row = self.entries().get(sid)
        if not row or row["access"] != "available":
            raise ValueError("source is unavailable")
        text = source_text(row["text_path"])
        if hashlib.sha256(text.encode()).hexdigest() != row["fingerprint"]:
            raise ValueError("source changed; refresh the inventory before reading or citing it")
        return "\n".join(f"{n}: {line}" for n, line in enumerate(text.splitlines(), 1) if start <= n < start + lines)

    def sample(self, count=12):
        buckets = defaultdict(list)
        for row in self.entries().values():
            if row["role"] != "voice" or row["access"] != "available" or row.get("duplicate_of") or row["authorship"] != "confirmed":
                continue
            period = str(row.get("published_at") or "unknown")[:4]
            buckets[(row["medium"], period)].append(row)
        queues = []
        for key in sorted(buckets):
            rows = sorted(buckets[key], key=lambda r: (r["words"], r["id"]))
            mixed = []
            while rows:
                mixed.append(rows.pop())
                if rows:
                    mixed.append(rows.pop(0))
            queues.append(deque(mixed))
        result = []
        while queues and len(result) < count:
            for queue in queues:
                if queue and len(result) < count:
                    result.append(queue.popleft())
            queues = [q for q in queues if q]
        return result

    def save_profile(self, draft):
        text = Path(draft).expanduser().read_text(encoding="utf-8")
        if not text.strip() or len(text) > 16000:
            raise ValueError("profile must contain 1-16000 characters")
        citations = set(re.findall(r"source:([a-f0-9]{16})\b", text))
        if not citations:
            raise ValueError("profile needs source:<id> evidence references")
        with self.locked():
            entries = self.entries()
            for sid in citations:
                row = entries.get(sid)
                if not row or row["role"] == "reference" or row["authorship"] != "confirmed" or row["access"] != "available" or row["read_status"] not in {"excerpt", "full"}:
                    raise ValueError(f"profile evidence {sid} must be read, available, confirmed subject material")
                current = hashlib.sha256(source_text(row["text_path"]).encode()).hexdigest()
                if current != row["fingerprint"]:
                    raise ValueError("source changed; refresh and review it before saving a profile")
            atomic_write(self.folder / "profile.md", text)
            meta = self.metadata()
            meta.update(profile_stale=False, profile_updated_at=now(),
                        profile_sources={sid: entries[sid]["fingerprint"] for sid in sorted(citations)})
            self.save(entries, meta)
        return str(self.folder / "profile.md")

    def status(self):
        rows = list(self.entries().values())
        return {**self.metadata(), "profile_path": str(self.folder / "profile.md"),
                "sources": len(rows), "access": dict(Counter(r["access"] for r in rows)),
                "reading": dict(Counter(r["read_status"] for r in rows)),
                "duplicates": sum(bool(r.get("duplicate_of")) for r in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--subject", required=True, help="Stable, separate lowercase subject slug")
    commands = parser.add_subparsers(dest="command", required=True)
    inv = commands.add_parser("inventory")
    inv.add_argument("paths", nargs="*")
    inv.add_argument("--manifest", action="append", default=[])
    inv.add_argument("--name")
    inv.add_argument("--role", choices=ROLES, default="voice")
    inv.add_argument("--author", default="")
    inv.add_argument("--authorship", choices=("confirmed", "unknown", "ai"), default="unknown")
    sample = commands.add_parser("sample")
    sample.add_argument("--count", type=int, default=12)
    read = commands.add_parser("read")
    read.add_argument("source")
    read.add_argument("--start", type=int, default=1)
    read.add_argument("--lines", type=int, default=120)
    mark = commands.add_parser("mark-read")
    mark.add_argument("source")
    mark.add_argument("--level", choices=("excerpt", "full"), required=True)
    mark.add_argument("--note", default="")
    profile = commands.add_parser("save-profile")
    profile.add_argument("draft")
    commands.add_parser("status")
    args = parser.parse_args(argv)
    try:
        library = Library(args.library, args.subject)
        if args.command == "inventory":
            result = library.inventory(args.paths, args.manifest, args.role, args.author, args.authorship, args.name)
        elif args.command == "sample":
            if args.count < 1:
                raise ValueError("count must be positive")
            result = library.sample(args.count)
        elif args.command == "read":
            if args.start < 1 or args.lines < 1:
                raise ValueError("start and lines must be positive")
            print(library.read(args.source, args.start, args.lines))
            return 0
        elif args.command == "mark-read":
            library.mark_read(args.source, args.level, args.note)
            result = library.status()
        elif args.command == "save-profile":
            result = {"profile_path": library.save_profile(args.draft)}
        else:
            result = library.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f"corpus: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
