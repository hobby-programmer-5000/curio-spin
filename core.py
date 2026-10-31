"""CurioSpin core logic: normalization, similarity, reel arrangement (spreading similar keywords apart)
and file parsing.

Independent of the GUI so it can be tested on its own. Standard library only - no models, no packages.
"""

import csv
import io
import random
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_ZERO_WIDTH = re.compile("[​-‏⁠﻿]")
_WS = re.compile(r"\s+")
_SEPARATORS = re.compile(r"[\s\-_/\\.,;:|·・()\[\]{}<>\"'`~!?@#$%^&*+=]+")


def clean(s):
    """Display form: Unicode NFKC, collapsed whitespace, surrounding quotes removed."""
    s = _ZERO_WIDTH.sub("", str(s))
    s = unicodedata.normalize("NFKC", s)
    s = _WS.sub(" ", s).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def key(s):
    """Duplicate-check key (ignores case, extra spaces and full-width forms)."""
    return clean(s).casefold()


def dedupe(words):
    seen, out = set(), []
    for w in words:
        w = clean(w)
        k = w.casefold()
        if k and k not in seen:
            seen.add(k)
            out.append(w)
    return out


# ---------------------------------------------------------------------------
# Similarity (character n-grams + Hangul jamo n-grams + tokens + containment/prefix/suffix)
# ---------------------------------------------------------------------------


def to_jamo(s):
    """Decompose Hangul syllables into initial/medial/final jamo (pure Unicode arithmetic)."""
    out = []
    for ch in s:
        c = ord(ch)
        if 0xAC00 <= c <= 0xD7A3:
            c -= 0xAC00
            out.append(chr(0x1100 + c // 588))
            out.append(chr(0x1161 + (c % 588) // 28))
            if c % 28:
                out.append(chr(0x11A7 + c % 28))
        else:
            out.append(ch)
    return "".join(out)


def _ngrams(s, n):
    s = "^" + s + "$"
    if len(s) <= n:
        return frozenset((s,))
    return frozenset(s[i:i + n] for i in range(len(s) - n + 1))


@dataclass(frozen=True)
class Features:
    compact: str
    grams: frozenset
    jamo: frozenset
    tokens: frozenset


# Korean particles stripped from the end of a token. Endings that are easily confused with the
# last syllable of a noun (은/는/이/가/로 ...) are deliberately left out.
_PARTICLES = ("에서의", "와의", "과의", "에서", "의", "와", "과")
_STOP_TOKENS = {"그리고", "및", "대", "the", "of", "and", "a", "an", "in", "on", "for", "to"}


def _token(tok):
    for p in _PARTICLES:
        if tok.endswith(p) and len(tok) - len(p) >= 2:
            return tok[:-len(p)]
    return tok


def features(s):
    k = key(s)
    parts = [p for p in _SEPARATORS.split(k) if p]
    compact = "".join(parts)
    tokens = frozenset(tok for tok in (_token(p) for p in parts) if tok not in _STOP_TOKENS)
    return Features(compact, _ngrams(compact, 2), _ngrams(to_jamo(compact), 3), tokens)


def _significant(tok):
    return not tok.isdigit() and len(tok) >= (4 if tok.isascii() else 2)


def _dice(a, b):
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def _common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def similarity_f(fa, fb):
    """Similarity between two Features, 0..1."""
    a, b = fa.compact, fb.compact
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    shared = fa.tokens & fb.tokens
    union = fa.tokens | fb.tokens
    tok = len(shared) / len(union) if union else 0.0
    score = 0.45 * _dice(fa.grams, fb.grams) + 0.35 * _dice(fa.jamo, fb.jamo) + 0.20 * tok

    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    # a meaningful shared word ("Mozart's Requiem" / "Wolfgang Amadeus Mozart")
    sig = [s for s in shared if _significant(s)]
    if sig:
        score = max(score, 0.45 + 0.35 * min(1.0, max(map(len, sig)) / len(short)))
    if len(short) >= 2 and short in long_:  # "apple" in "appletree"
        score = max(score, 0.55 + 0.45 * len(short) / len(long_))
    pre = _common_prefix(a, b)  # "dogfood" / "dogtoys"
    if pre >= 2:
        score = max(score, 0.75 * pre / len(short))
    suf = _common_prefix(a[::-1], b[::-1])  # "dogfood" / "catfood"
    if suf >= 2:
        score = max(score, 0.6 * suf / len(short))
    return min(1.0, score)


def similarity(a, b):
    return similarity_f(features(a), features(b))


# ---------------------------------------------------------------------------
# Reel arrangement: random, but similar keywords are kept apart
# ---------------------------------------------------------------------------

# weight of a keyword pair that is d slots apart on the reel (the range visible at the same time)
NEIGHBOR_WEIGHTS = (1.0, 0.5, 0.25)
# same group (a field/category column in the CSV): add this share of the remaining similarity headroom
GROUP_SIM = 0.35


class _SimCache:
    def __init__(self, items, groups=None):
        self.f = [features(x) for x in items]
        self.g = [groups.get(x) for x in items] if groups else None
        self.c = {}

    def __call__(self, i, j):
        if i == j:
            return 1.0
        k = (i, j) if i < j else (j, i)
        v = self.c.get(k)
        if v is None:
            v = similarity_f(self.f[i], self.f[j])
            if self.g and self.g[i] and self.g[i] == self.g[j]:
                v += (1.0 - v) * GROUP_SIM
            self.c[k] = v
        return v


def arrange(items, rng=None, time_budget=0.35, weights=NEIGHBOR_WEIGHTS, groups=None):
    """Order keywords randomly around a circular reel while keeping nearby slots dissimilar.

    groups: {keyword: group name}. When given, keywords of the same group also count as similar.

    1) Randomized greedy construction: sample some remaining keywords and pick, at random, one of
       those whose similarity to the last few placed keywords is (near) the lowest.
    2) Local improvement: swap two random slots and keep the swap if the local cost does not go up.
       Repeats within the time budget.
    """
    items = list(items)
    n = len(items)
    rng = rng or random.Random()
    if n <= 3:
        rng.shuffle(items)
        return items

    deadline = time.perf_counter() + time_budget
    sim = _SimCache(items, groups)
    w_count = max(1, min(len(weights), (n - 1) // 2))
    w = weights[:w_count]

    # 1) randomized greedy construction
    remaining = list(range(n))
    rng.shuffle(remaining)
    order = [remaining.pop()]
    pool = max(4, min(48, 60000 // n))
    while remaining:
        if time.perf_counter() > deadline:
            pool = 3  # over budget: finish almost purely at random
        m = len(remaining)
        cand = rng.sample(range(m), pool) if m > pool else range(m)
        scored = []
        for p in cand:
            c = remaining[p]
            s = 0.0
            for d in range(min(w_count, len(order))):
                s += w[d] * sim(c, order[-1 - d])
            scored.append((s, p))
        best = min(s for s, _ in scored)
        p = rng.choice([p for s, p in scored if s <= best + 0.04])
        remaining[p], remaining[-1] = remaining[-1], remaining[p]
        order.append(remaining.pop())

    # 2) swap-based local improvement (circular)
    def local_cost(positions):
        pairs = set()
        for i in positions:
            for d in range(1, w_count + 1):
                pairs.add((i, d))
                pairs.add(((i - d) % n, d))
        return sum(w[d - 1] * sim(order[x], order[(x + d) % n]) for x, d in pairs)

    max_iters = 40 * n
    improve_deadline = time.perf_counter() + time_budget
    it = 0
    while it < max_iters:
        if not it & 63 and time.perf_counter() > improve_deadline:
            break
        it += 1
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        before = local_cost((i, j))
        order[i], order[j] = order[j], order[i]
        if local_cost((i, j)) > before:
            order[i], order[j] = order[j], order[i]

    return [items[i] for i in order]


def neighbor_cost(order, weights=NEIGHBOR_WEIGHTS, groups=None):
    """Quality metric: weighted mean similarity of neighboring pairs on the circular reel (lower is better)."""
    n = len(order)
    if n < 2:
        return 0.0
    sim = _SimCache(order, groups)
    w_count = max(1, min(len(weights), (n - 1) // 2))
    total = wsum = 0.0
    for i in range(n):
        for d in range(1, w_count + 1):
            total += weights[d - 1] * sim(i, (i + d) % n)
            wsum += weights[d - 1]
    return total / wsum


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------


def decode_bytes(data):
    """Decode trying BOM, UTF-8, then CP949 (Korean Excel CSV). Returns (text, encoding)."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "UTF-16"
    for enc, label in (("utf-8-sig", "UTF-8"), ("cp949", "CP949")):
        try:
            return data.decode(enc), label
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1"), "Latin-1"


def read_file_text(path):
    with open(path, "rb") as fh:
        return decode_bytes(fh.read())


def split_manual(text, split_commas=True):
    """Manual input: split on newlines (and commas/tabs)."""
    out = []
    for line in text.splitlines():
        parts = re.split(r"[,\t]", line) if split_commas else line.split("\t")
        out.extend(p for p in (clean(x) for x in parts) if p)
    return dedupe(out)


def parse_txt(text):
    """TXT: one keyword per line, '#' lines are comments. A single-line file is also split on commas."""
    lines = [ln for ln in text.splitlines() if clean(ln) and not clean(ln).startswith("#")]
    return split_manual("\n".join(lines), split_commas=len(lines) <= 1)


def read_csv_rows(text, delimiter=None):
    """CSV text to a list of rows. delimiter=None means auto-detect."""
    if delimiter is None:
        sample = text[:20000]
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            counts = {d: sample.count(d) for d in ",;\t|"}
            best = max(counts, key=counts.get)
            delimiter = best if counts[best] else ","
    rows = []
    for r in csv.reader(io.StringIO(text), delimiter=delimiter):
        r = [clean(c) for c in r]
        while r and not r[-1]:
            r.pop()
        rows.append(r)
    while rows and not rows[-1]:
        rows.pop()
    return rows, delimiter


_NUM = re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?%?$")
_DATE = re.compile(
    r"^(\d{2,4}\s?[-./년]\s?\d{1,2}\s?[-./월]\s?\d{1,2}\s?일?\.?)?\s*(\d{1,2}:\d{2}(:\d{2})?)?$"
)
_URL = re.compile(r"^(https?://|www\.)\S+$|^[\w.+-]+@[\w-]+\.[\w.]+$", re.I)


def cell_kind(v):
    v = v.strip()
    if not v:
        return "empty"
    if _NUM.match(v):
        return "num"
    if _DATE.match(v):
        return "date"
    if _URL.match(v):
        return "url"
    return "text"


# Header name hints: names of keyword columns / names of columns unrelated to keywords.
KEYWORD_HINTS = {
    "키워드", "keyword", "keywords", "단어", "word", "words", "태그", "tag", "tags", "검색어",
    "query", "term", "terms", "용어", "주제", "topic", "topics", "항목", "item", "items", "이름",
    "name", "제목", "title", "후보", "candidate", "메뉴", "menu", "표현", "phrase", "문구",
}
OTHER_HINTS = {
    "번호", "no", "id", "#", "순번", "순서", "index", "idx", "날짜", "일자", "date", "시간", "time",
    "비고", "메모", "memo", "note", "notes", "설명", "description", "desc", "비율", "점수", "score",
    "count", "개수", "수량", "횟수", "검색량", "조회수", "volume", "url", "링크", "link", "분류",
    "카테고리", "category", "구분", "type", "rank", "순위", "등록일", "작성자", "author", "가격",
    "price", "금액", "합계", "total", "상태", "status", "출처", "source",
}
# Names of columns holding a keyword's field/category (used as groups to avoid clustering)
GROUP_HINTS = {
    "분야", "분류", "카테고리", "category", "구분", "type", "field", "장르", "genre", "group", "그룹",
    "유형", "class", "대분류", "중분류", "소분류",
}
OTHER_HINTS |= GROUP_HINTS


def _header_key(cell):
    return "".join(p for p in _SEPARATORS.split(key(cell)) if p) or key(cell)


def hint_class(cell):
    """Whether a header name looks like a keyword column ('kw'), an unrelated column ('other'), or unknown (None)."""
    k = _header_key(cell)
    if not k:
        return None
    if k in KEYWORD_HINTS:
        return "kw"
    if k in OTHER_HINTS:
        return "other"
    # substring match: in Korean compound nouns the head word comes last, so the hint ending last wins
    best = None
    for hints, cls in ((KEYWORD_HINTS, "kw"), (OTHER_HINTS, "other")):
        for h in hints:
            if len(h) < 2 or (h.isascii() and len(h) <= 3):
                continue
            pos = k.rfind(h)
            if pos >= 0:
                cand = (pos + len(h), len(h), cls)
                if best is None or cand[:2] > best[:2]:
                    best = cand
    return best[2] if best else None


@dataclass
class ColumnInfo:
    index: int
    header: str
    kinds: Counter = field(default_factory=Counter)
    avg_len: float = 0.0
    distinct: int = 0

    @property
    def filled(self):
        return sum(v for k, v in self.kinds.items() if k != "empty")

    @property
    def text_ratio(self):
        return self.kinds["text"] / self.filled if self.filled else 0.0

    def dominant_kind(self):
        """'num' / 'date' / 'url' / 'text', or 'empty' for a column with no values."""
        if not self.filled:
            return "empty"
        return max(((k, v) for k, v in self.kinds.items() if k != "empty"), key=lambda kv: kv[1])[0]


@dataclass
class Layout:
    skip_top: int
    has_header: bool
    selected: list
    columns: list
    group_col: int = None


def column_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def analyze_columns(rows, skip_top, has_header):
    ncols = max((len(r) for r in rows), default=0)
    head = rows[skip_top] if has_header and skip_top < len(rows) else []
    body = rows[skip_top + (1 if has_header else 0):][:1000]
    cols = []
    for ci in range(ncols):
        info = ColumnInfo(ci, head[ci] if ci < len(head) else "")
        lens, values = [], set()
        for r in body:
            v = r[ci] if ci < len(r) else ""
            info.kinds[cell_kind(v)] += 1
            if v:
                lens.append(len(v))
                values.add(key(v))
        info.avg_len = sum(lens) / len(lens) if lens else 0.0
        info.distinct = len(values)
        cols.append(info)
    return cols


def auto_select(columns, has_header):
    if has_header:
        kw = [c.index for c in columns if hint_class(c.header) == "kw"]
        if kw:
            return kw
    sel = [
        c.index for c in columns
        if c.filled and c.text_ratio >= 0.6 and c.avg_len <= 40
        and not (has_header and hint_class(c.header) == "other")
    ]
    if not sel and columns:
        best = max(columns, key=lambda c: (c.kinds["text"], -c.index))
        sel = [best.index]
    return sel


def detect_layout(rows):
    """Guess the title rows to skip, whether there is a header, and the keyword columns."""
    filled_rows = [r for r in rows if any(r)]
    if not filled_rows:
        return Layout(0, False, [], [])
    body_width = Counter(len(r) for r in filled_rows).most_common(1)[0][0]

    # skip blank rows and (in multi-column CSVs) single-cell title rows at the top
    skip = 0
    for r in rows[:10]:
        n_filled = sum(1 for c in r if c)
        if n_filled == 0 or (body_width >= 2 and n_filled == 1 and len(r) < body_width):
            skip += 1
        else:
            break
    if skip >= len(rows):
        skip = 0

    first = rows[skip]
    body = [r for r in rows[skip + 1:] if any(r)][:300]
    has_header = any(hint_class(c) for c in first if c)
    if not has_header and body:
        # a text cell on top of a column that is mostly numbers/dates/links is a header
        for ci, c in enumerate(first):
            if cell_kind(c) != "text":
                continue
            kinds = [cell_kind(r[ci]) for r in body if ci < len(r) and r[ci]]
            if kinds and sum(k != "text" for k in kinds) / len(kinds) >= 0.8:
                has_header = True
                break

    columns = analyze_columns(rows, skip, has_header)
    selected = auto_select(columns, has_header)
    return Layout(skip, has_header, selected, columns, detect_group_column(columns, selected, has_header))


def detect_group_column(columns, selected, has_header):
    """Guess the field/category column: a category-like header name, or short text values that repeat."""
    best = None
    for c in columns:
        if c.index in selected or c.filled < 4 or c.distinct < 2:
            continue
        hinted = has_header and _header_key(c.header) in GROUP_HINTS and c.text_ratio >= 0.5
        repetitive = c.text_ratio >= 0.8 and c.avg_len <= 20 and c.distinct <= c.filled // 3
        if hinted or repetitive:
            rank = (hinted, -c.distinct)
            if best is None or rank > best[0]:
                best = (rank, c.index)
    return best[1] if best else None


def extract_entries(rows, skip_top, has_header, columns, drop_numeric=True,
                    drop_header_repeats=True, exclude=(), group_col=None):
    """Extract (keyword, group) pairs from the chosen columns, in row order, without duplicates.
    The group is '' when there is no group column."""
    excl = {key(x) for x in exclude if key(x)}
    header_keys = set()
    if has_header and skip_top < len(rows):
        head = rows[skip_top]
        header_keys = {key(head[c]) for c in columns if c < len(head) and head[c]}
    out, seen = [], set()
    for r in rows[skip_top + (1 if has_header else 0):]:
        group = clean(r[group_col]) if group_col is not None and group_col < len(r) else ""
        for c in columns:
            if c >= len(r):
                continue
            v = clean(r[c])
            k = v.casefold()
            if not k or k in seen or k in excl:
                continue
            if drop_header_repeats and k in header_keys:
                continue
            if drop_numeric and cell_kind(v) in ("num", "date"):
                continue
            seen.add(k)
            out.append((v, group))
    return out


def extract_keywords(rows, skip_top, has_header, columns, drop_numeric=True,
                     drop_header_repeats=True, exclude=()):
    return [k for k, _ in extract_entries(rows, skip_top, has_header, columns, drop_numeric,
                                          drop_header_repeats, exclude)]
