**English** | [한국어](how-it-works.ko.md)

# How CurioSpin works

CurioSpin has four jobs:

1. Pick a winner fairly.
2. Animate a slot reel that lands on that winner.
3. Order the reel so that similar keywords are never shown next to each other.
4. Turn messy CSV/TXT files into a clean keyword list.

All of it is plain Python standard library. There are no machine-learning models, embeddings or network calls. The logic lives in [`core.py`](../core.py) and is covered by [`test_core.py`](../test_core.py).

---

## 1. A fair draw comes first

The winner is chosen **before** anything moves:

```python
winner = random.SystemRandom().choice(candidates)
```

`SystemRandom` uses the operating system's cryptographic random source, so every candidate has exactly `1/n` chance. The reel order (section 3) is decided afterwards and only controls what you *see* while it spins. The order never changes who wins, so the anti-clustering logic cannot bias the result.

## 2. The reel animation

The reel is a circular list of keywords drawn on a Tk `Canvas`. Its position `pos` is a real number: the integer part is the keyword in the center and the fraction is the scroll offset. Five rows are visible, and text fades toward the background color as it moves away from the center line.

To land on the winner at index `t` starting from position `p0`:

```
Δ        = (t − p0) mod n                      # distance to the winner within one lap
rows_min = 11 × duration                       # so the reel visibly spins
D        = Δ + n × ceil((rows_min − Δ) / n)    # whole laps + Δ, always ≥ rows_min
```

The position over normalized time `u ∈ [0, 1]` is an ease-out curve with a small "bounce" at the end:

```
pos(u) = p0 + D × (1 − (1 − u)^4)
       + 0.22 × sin(π × (u − 0.8) / 0.2)        only when u > 0.8
```

At `u = 1` the bounce term is 0 and `pos = p0 + D` is exactly on the winner. Frames are scheduled every ~12 ms.

## 3. Keeping similar keywords apart

### 3.1 Similarity between two keywords (0 … 1)

Each keyword is first normalized: Unicode NFKC, case-folded, zero-width characters removed, whitespace collapsed. Then three feature sets are built:

| Feature | Example: `모차르트의 레퀴엠` / `Mozart's Requiem` | Catches |
|---|---|---|
| Character bigrams of the text without separators, with `^`/`$` boundary marks | `^모, 모차, 차르, …` | spelling overlap |
| **Hangul jamo** trigrams: each syllable split into initial/medial/final letters by Unicode arithmetic (`(code − 0xAC00) → 588, 28`) | `ㅁㅗㅊ, ㅗㅊㅏ, …` | near spellings in Korean (`강아지` / `강아쥐`) |
| Tokens (words) with Korean particles removed (`의 와 과 에서 …`) and stop words dropped | `{모차르트, 레퀴엠}` | shared names regardless of particles or word order |

The base score is a weighted mix:

```
base = 0.45 × Dice(bigrams) + 0.35 × Dice(jamo trigrams) + 0.20 × Jaccard(tokens)
```

Several structural rules can raise it (the maximum wins):

| Rule | Score | Example |
|---|---|---|
| A meaningful shared word (≥2 Hangul or ≥4 Latin characters, not just digits) | `0.45 + 0.35 × len(word) / len(shorter)` | *Mozart's Requiem* / *Wolfgang Amadeus Mozart* |
| One keyword contains the other | `0.55 + 0.45 × len(short) / len(long)` | *Plato* / *Plato's Allegory of the Cave* |
| Common prefix of ≥2 characters | `0.75 × prefix / len(shorter)` | `강아지사료` / `강아지간식` |
| Common suffix of ≥2 characters | `0.60 × suffix / len(shorter)` | `강아지사료` / `고양이사료` |

Korean particles are trimmed only when at least two characters remain, and only for endings that are rarely the last syllable of a noun. `의/와/과` are trimmed, but `은/는/이/가/로` are not (they would turn `피에로` into `피에`).

**Fields.** If the CSV has a field/category column, two keywords from the same field get extra similarity:

```
s' = s + (1 − s) × 0.35
```

Same-field keywords then repel each other a little, and very similar texts still repel the most.

### 3.2 Arranging the reel

The reel is circular, and a keyword is visible together with its neighbors up to 2–3 slots away. So the cost of an order `o` is:

```
cost(o) = Σ_i  Σ_{d=1..3}  w_d × sim(o_i, o_{(i+d) mod n}),    w = (1, 0.5, 0.25)
```

Minimizing this exactly is a hard combinatorial problem (similar to the traveling salesman problem). A good result in a fraction of a second is enough, and it also has to stay **random**. So the search has two phases.

1. **Randomized greedy construction.** Start from a random keyword. At each step, sample up to `clamp(60000 / n, 4, 48)` of the remaining keywords and score each one by its weighted similarity to the last 3 placed keywords. Then pick **at random** among those within `best + 0.04`. Sampling keeps large lists fast, and the random tie-break keeps every spin different.
2. **Local search by random swaps.** Swap two random slots and recompute only the pairs around those two slots. Keep the swap if the cost did not increase. This repeats up to `40 × n` times or until the time budget runs out (0.15 s in the app). Accepting equal-cost swaps keeps the order drifting randomly.

A fresh order is built on every spin. The reel is rotated so the keyword currently in the center stays put, which avoids a visible jump.

**Measured on a 361-topic list with 7 fields:**

| | Random shuffle | CurioSpin |
|---|---|---|
| Same-field neighbors (distance 1) | 46 | **0** |
| Highest text similarity between adjacent keywords | 0.62 | **0.00** |
| Same field 7 slots apart (would be ~100% for a fixed rotation) | ~14% | 11% |

The last row shows the fields do *not* settle into a predictable rotation like History → Literature → Art…. Arranging 3,000 keywords takes under a second.

## 4. CSV / TXT preprocessing

### Decoding
1. A UTF-16 BOM means UTF-16.
2. Otherwise try UTF-8 (BOM optional).
3. Then CP949, the encoding Korean Excel uses for "CSV" files.
4. If everything fails, Latin-1 (never fails).

### Delimiter
`csv.Sniffer` chooses among `,` `;` tab `|`. If it can't decide, the most frequent of those characters is used.

### Title rows
Blank rows and single-cell rows within the first 10 rows are skipped, but only when typical rows have two or more cells. This catches files that start with a title like "Keyword list 2026".

### Header row
The first row is treated as a header when either of these holds:
- A cell matches a known column name, such as *keyword, topic, name* or *no, id, date, count, category, field*, in English or Korean. For compound Korean names, the hint that ends **last** wins, because Korean compounds put the head noun at the end. `검색 키워드` ("search keyword") is a keyword column, while `키워드 검색량` ("keyword search volume") is not.
- A text cell sits on top of a column whose values are ≥80% numbers, dates or links.

### Keyword columns
- Columns whose header looks like a keyword column are used.
- If there are none, mostly-text columns (≥60% text, average length ≤40) are used, except those named like IDs, dates, notes or categories.

### Field column
A column that isn't a keyword column is used as the field column if:
- its name is category-like (*field, category, genre, 분야, 분류 …*), or
- its values are short (≤20 characters), mostly text, and repeat (distinct values ≤ ⅓ of the rows).

### Filters
- Values that are only numbers or dates are dropped.
- Values equal to the header (repeated header rows) are dropped.
- Words you list are dropped.
- Duplicates are removed by NFKC + case-folded comparison.

Every guess is shown in the import preview and can be changed before importing.

## 5. Portability

- The app is a single executable built with PyInstaller in `--onefile --windowed` mode. Python and Tk are bundled inside.
- State (lists, history, field mapping, language, options) is saved to `keyword_slot_data.json` next to the exe. If that folder is read-only, it goes to `%APPDATA%\CurioSpin\` instead. Writes go to a temporary file first and are then moved into place, so a crash can't corrupt the data file.
- The UI is DPI-aware, and all pixel sizes scale with the screen DPI.
