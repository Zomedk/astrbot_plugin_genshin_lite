"""A dependency-free Chinese character n-gram SQLite FTS5 search engine.

Use this module from both the offline index builder and the AstrBot plugin.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

CHINESE = re.compile(r"[\u3400-\u9fff]+")
WORDS = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,}")
# These are different organization names, even though one contains the other.
MAGICIANS_ASSEMBLY = re.compile(r"(?<![小大])魔女会")


def tokens(text: str, *, max_count: int | None = None) -> list[str]:
    """Use Chinese bigrams/trigrams and Latin words; no jieba needed."""
    seen: set[str] = set()
    out: list[str] = []
    # Prefer longer Chinese sequences (proper nouns and short phrases).
    for sequence in sorted(CHINESE.findall(text), key=len, reverse=True):
        for n in (3, 2):
            if len(sequence) >= n:
                for i in range(len(sequence) - n + 1):
                    term = sequence[i : i + n]
                    if term not in seen:
                        seen.add(term)
                        out.append(term)
    for term in WORDS.findall(text.lower()):
        if term not in seen:
            seen.add(term)
            out.append(term)
    return out if max_count is None else out[:max_count]


def create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE docs (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            source_path TEXT NOT NULL,
            chunk_no INTEGER NOT NULL,
            content TEXT NOT NULL
        );
        CREATE INDEX idx_docs_source ON docs(source_path);
        CREATE VIRTUAL TABLE doc_index USING fts5(
            terms, tokenize='unicode61', content=''
        );
        """
    )


def search(db_path: Path, query: str, *, limit: int = 5, max_chars: int = 440) -> list[dict]:
    if not db_path.is_file():
        raise FileNotFoundError(f"未找到索引库: {db_path}")
    terms = tokens(query, max_count=22)
    if not terms:
        return []
    distinct_assembly = bool(MAGICIANS_ASSEMBLY.search(query))
    # Terms only contain Chinese chars and safe Latin alnum/underscore/hyphen.
    # Quote tokens so hyphens do not become FTS5 operators.
    match = ('"魔女会"' if distinct_assembly else
             " OR ".join('"' + s.replace('"', '""') + '"' for s in terms))
    with sqlite3.connect(str(db_path), timeout=10) as con:
        con.execute("PRAGMA query_only = ON")
        rows = con.execute(
            """
            SELECT d.category, d.title, d.source_path, d.chunk_no, d.content,
                   bm25(doc_index) AS rank
              FROM doc_index
              JOIN docs AS d ON d.id = doc_index.rowid
             WHERE doc_index MATCH ?
             ORDER BY rank ASC
             LIMIT 250
            """, (match,)
        ).fetchall()

    q = query.strip().lower()
    # The inverse document frequency signal is already included in bm25.
    # Give small deterministic boosts for source titles and literal substrings.
    results = []
    for category, title, source, chunk_no, content, rank in rows:
        lower = content.lower()
        title_lower = title.lower()
        assembly_match = MAGICIANS_ASSEMBLY.search(content) if distinct_assembly else None
        if distinct_assembly and not (assembly_match or MAGICIANS_ASSEMBLY.search(title)):
            continue
        match_count = sum(1 for t in terms if t in lower)
        literal = 1 if len(q) >= 2 and q in lower else 0
        title_hit = sum(1 for t in terms if t in title_lower)
        score = (-rank) + 0.15 * match_count + 0.4 * title_hit + 2.0 * literal
        if distinct_assembly:
            score += 2.0 * sum(t in lower or t in title_lower for t in terms if t != "魔女会")
            if "「魔女会」" in content or "《魔女会》" in content:
                score += 1.0
        # Show short but useful evidence near the first query match.
        at = (assembly_match.start() if assembly_match else
              next((lower.find(t) for t in terms if t in lower), 0))
        begin = max(0, at - 70)
        snippet = content[begin : begin + max_chars].strip()
        if begin:
            snippet = "…" + snippet
        if begin + max_chars < len(content):
            snippet += "…"
        results.append({
            "category": category,
            "title": title,
            "path": source,
            "chunk": chunk_no,
            "text": snippet,
            "_score": score,
        })
    results.sort(key=lambda x: x["_score"], reverse=True)
    wanted = max(1, min(limit, 8))
    selected = []
    source_counts: dict[str, int] = {}
    for hit in results:
        if source_counts.get(hit["path"], 0) >= 2:
            continue
        selected.append(hit)
        source_counts[hit["path"]] = source_counts.get(hit["path"], 0) + 1
        if len(selected) == wanted:
            break
    if len(selected) < wanted:
        selected_ids = {id(hit) for hit in selected}
        selected.extend(hit for hit in results if id(hit) not in selected_ids)
    for x in selected[:wanted]:
        x.pop("_score", None)
    return selected[:wanted]
