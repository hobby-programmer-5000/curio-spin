"""CurioSpin - spin your keywords like a slot machine and draw one at random."""

import json
import math
import os
import random
import sys
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import core
import i18n
from i18n import t

APP_NAME = "CurioSpin"
FONT = "Malgun Gothic"
DATA_FILE = "keyword_slot_data.json"

# reel colors
REEL_BG = "#1b1d24"
REEL_BAND = "#2a2e3a"
REEL_FLASH = "#5a4a12"
GOLD = "#f5c542"
SOFT = "#c9ccd6"
TEXT_HI = (255, 255, 255)
TEXT_LO = (60, 64, 76)

SPEEDS = {"short": 2.2, "normal": 3.6, "long": 5.5}
LEGACY_SPEEDS = {"짧게": "short", "보통": "normal", "길게": "long"}  # values saved by older versions
DELIMS = (("delim_auto", None), ("delim_comma", ","), ("delim_semicolon", ";"), ("delim_tab", "\t"),
          ("delim_pipe", "|"))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c)) for c in rgb)


def _lerp(a, b, f):
    return tuple(x + (y - x) * f for x, y in zip(a, b))


def data_path():
    """Portable: save next to the executable, or under %APPDATA% if that folder is not writable."""
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    path = os.path.join(base, DATA_FILE)
    if os.access(path, os.W_OK) or (not os.path.exists(path) and os.access(base, os.W_OK)):
        return path
    alt = os.path.join(os.environ.get("APPDATA", base), APP_NAME)
    os.makedirs(alt, exist_ok=True)
    return os.path.join(alt, DATA_FILE)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


class Store:
    def __init__(self):
        self.candidates = []
        self.excluded = []
        self.history = []  # [(timestamp string, keyword)]
        self.groups = {}  # {keyword: field} - only for keywords imported with a field column

    def keys(self):
        return {core.key(x) for x in self.candidates + self.excluded}

    def add(self, words, groups=None):
        keys = self.keys()
        added = dup = 0
        for raw in words:
            w = core.clean(raw)
            k = w.casefold()
            if not k:
                continue
            if k in keys:
                dup += 1
                continue
            keys.add(k)
            self.candidates.append(w)
            if groups and groups.get(raw):
                self.groups[w] = groups[raw]
            added += 1
        return added, dup

    def label(self, w):
        g = self.groups.get(w)
        return f"{w}  · {g}" if g else w

    def exclude(self, words):
        for w in words:
            if w in self.candidates:
                self.candidates.remove(w)
                self.excluded.append(w)

    def restore(self, words):
        for w in words:
            if w in self.excluded:
                self.excluded.remove(w)
                self.candidates.append(w)

    def delete(self, words):
        for w in words:
            for lst in (self.candidates, self.excluded):
                if w in lst:
                    lst.remove(w)
            self.groups.pop(w, None)

    def to_dict(self):
        return {"candidates": self.candidates, "excluded": self.excluded,
                "history": [list(h) for h in self.history], "groups": self.groups}

    def load(self, d):
        self.candidates = [str(x) for x in d.get("candidates", [])]
        self.excluded = [str(x) for x in d.get("excluded", [])]
        self.history = [tuple(h) for h in d.get("history", []) if len(h) == 2]
        known = set(self.candidates) | set(self.excluded)
        self.groups = {str(k): str(v) for k, v in dict(d.get("groups", {})).items() if k in known and v}


# ---------------------------------------------------------------------------
# Slot reel
# ---------------------------------------------------------------------------


class Reel(tk.Canvas):
    VISIBLE = 5

    def __init__(self, master, scale):
        self.s = scale
        self.row_h = int(64 * scale)
        super().__init__(master, width=int(520 * scale), height=self.row_h * self.VISIBLE,
                         bg=REEL_BG, highlightthickness=0, bd=0)
        self.font = tkfont.Font(family=FONT, size=22, weight="bold")
        self.order = []
        self.pos = 0.0
        self.flash = False
        self._fit = {}
        self.bind("<Configure>", lambda e: (self._fit.clear(), self.redraw()))

    def set_order(self, order, keep=None, pos=None):
        self.order = list(order)
        if pos is not None:
            self.pos = pos
        else:
            self.pos = float(self.order.index(keep)) if keep in self.order else 0.0
        self.redraw()

    def current(self):
        if not self.order:
            return None
        return self.order[int(round(self.pos)) % len(self.order)]

    def _fit_text(self, text, max_w):
        hit = self._fit.get(text)
        if hit is None:
            hit = text
            if self.font.measure(text) > max_w:
                lo, hi = 0, len(text)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if self.font.measure(text[:mid] + "…") <= max_w:
                        lo = mid
                    else:
                        hi = mid - 1
                hit = text[:lo] + "…"
            self._fit[text] = hit
        return hit

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w, h = int(self["width"]), int(self["height"])
        cy, rh = h / 2, self.row_h
        line_w = max(2, int(2 * self.s))
        self.create_rectangle(0, cy - rh / 2, w, cy + rh / 2, width=0,
                              fill=REEL_FLASH if self.flash else REEL_BAND)
        if not self.order:
            self.create_text(w / 2, cy, text=t("reel_empty"), fill=_hex(_lerp(TEXT_LO, TEXT_HI, 0.5)),
                             font=(FONT, 14))
        else:
            n = len(self.order)
            base = math.floor(self.pos)
            frac = self.pos - base
            pad = int(36 * self.s)
            half = self.VISIBLE // 2 + 1
            for k in range(-half, half + 1):
                # as pos increases, keywords move down from the top
                y = cy - (k - frac) * rh
                dist = min(1.0, abs(y - cy) / (rh * 2.6))
                self.create_text(w / 2, y, text=self._fit_text(self.order[(base + k) % n], w - 2 * pad),
                                 fill=_hex(_lerp(TEXT_HI, TEXT_LO, dist)), font=self.font)
        # gold guide lines and side pointers
        for yy in (cy - rh / 2, cy + rh / 2):
            self.create_line(0, yy, w, yy, fill=GOLD, width=line_w)
        p = int(12 * self.s)
        self.create_polygon(0, cy - p, p * 1.3, cy, 0, cy + p, fill=GOLD, outline="")
        self.create_polygon(w, cy - p, w - p * 1.3, cy, w, cy + p, fill=GOLD, outline="")


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


class _Dialog(tk.Toplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.resizable(True, True)
        self.bind("<Escape>", lambda e: self.destroy())

    def show(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + (m.winfo_width() - self.winfo_width()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()


class InputDialog(_Dialog):
    """Manual input. A plain Text widget, so there is no autocomplete."""

    def __init__(self, master, on_submit):
        super().__init__(master, t("input_title"))
        self.on_submit = on_submit
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=t("input_hint")).pack(anchor="w")
        box = ttk.Frame(frm)
        box.pack(fill="both", expand=True, pady=(6, 6))
        self.text = tk.Text(box, width=44, height=12, font=(FONT, 12), wrap="none", undo=True)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.split_commas = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text=t("input_commas"), variable=self.split_commas).pack(anchor="w")
        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text=t("btn_close"), command=self.destroy).pack(side="right")
        ttk.Button(btns, text=t("btn_add"), command=self.submit).pack(side="right", padx=(0, 6))
        self.text.bind("<Control-Return>", lambda e: (self.submit(), "break")[1])
        self.show()
        self.text.focus_set()

    def submit(self):
        words = core.split_manual(self.text.get("1.0", "end"), self.split_commas.get())
        if not words:
            return
        self.on_submit(words, None)
        self.text.delete("1.0", "end")
        self.text.focus_set()


class CsvImportDialog(_Dialog):
    """CSV preprocessing: skip top rows, drop the header, pick keyword/field columns, filter values."""

    PREVIEW_ROWS = 200
    MAX_COL_CHECKS = 40

    def __init__(self, master, path, text, encoding, existing_keys, on_import):
        super().__init__(master, t("csv_title", name=os.path.basename(path)))
        self.text = text
        self.existing = existing_keys
        self.on_import = on_import
        self.rows = []
        self.columns = []
        self.col_vars = []
        self.result = []
        self.groups = {}
        self.group_choices = [t("none")]
        self._busy = False
        self.group_var = tk.StringVar(value=t("none"))

        self.delim_labels = [t(k) for k, _ in DELIMS]
        self.delim_var = tk.StringVar(value=self.delim_labels[0])
        self.skip_var = tk.IntVar(value=0)
        self.header_var = tk.BooleanVar(value=False)
        self.drop_num_var = tk.BooleanVar(value=True)
        self.drop_head_var = tk.BooleanVar(value=True)
        self.exclude_var = tk.StringVar()

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)

        # options
        opt = ttk.LabelFrame(root, text=t("csv_prep"), padding=8)
        opt.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(opt, text=t("csv_encoding", enc=encoding)).grid(row=0, column=0, sticky="w")
        ttk.Label(opt, text=t("csv_delim")).grid(row=0, column=1, sticky="e", padx=(16, 4))
        cb = ttk.Combobox(opt, textvariable=self.delim_var, values=self.delim_labels, width=12, state="readonly")
        cb.grid(row=0, column=2, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self.reparse())
        ttk.Label(opt, text=t("csv_skip")).grid(row=0, column=3, sticky="e", padx=(16, 4))
        ttk.Spinbox(opt, from_=0, to=50, width=5, textvariable=self.skip_var).grid(row=0, column=4, sticky="w")
        self.skip_var.trace_add("write", lambda *a: self.relayout())
        ttk.Checkbutton(opt, text=t("csv_header"), variable=self.header_var,
                        command=self.relayout).grid(row=0, column=5, sticky="w", padx=(16, 0))
        ttk.Checkbutton(opt, text=t("csv_drop_num"), variable=self.drop_num_var,
                        command=self.update_preview).grid(row=1, column=0, columnspan=2, sticky="w",
                                                          pady=(6, 0), padx=(0, 16))
        ttk.Checkbutton(opt, text=t("csv_drop_head"), variable=self.drop_head_var,
                        command=self.update_preview).grid(row=1, column=2, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(opt, text=t("csv_exclude")).grid(row=1, column=4, sticky="e", padx=(16, 4), pady=(6, 0))
        ttk.Entry(opt, textvariable=self.exclude_var, width=24).grid(row=1, column=5, sticky="ew", pady=(6, 0))
        self.exclude_var.trace_add("write", lambda *a: self.update_preview())

        # column selection
        self.col_frame = ttk.LabelFrame(root, text=t("csv_columns"), padding=8)
        self.col_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 8))

        # source preview
        raw = ttk.LabelFrame(root, text=t("csv_raw"), padding=4)
        raw.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        raw.rowconfigure(0, weight=1)
        raw.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(raw, show="headings", height=14)
        ys = ttk.Scrollbar(raw, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(raw, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.tree.tag_configure("skip", foreground="#a0a0a0")
        self.tree.tag_configure("header", background="#fff2b3")

        # result preview
        res = ttk.LabelFrame(root, text=t("csv_result"), padding=4)
        res.grid(row=2, column=1, sticky="nsew")
        res.rowconfigure(1, weight=1)
        res.columnconfigure(0, weight=1)
        self.count_label = ttk.Label(res, text="")
        self.count_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.result_list = tk.Listbox(res, font=(FONT, 10), activestyle="none", width=26)
        rs = ttk.Scrollbar(res, orient="vertical", command=self.result_list.yview)
        self.result_list.configure(yscrollcommand=rs.set)
        self.result_list.grid(row=1, column=0, sticky="nsew")
        rs.grid(row=1, column=1, sticky="ns")

        btns = ttk.Frame(root)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text=t("btn_cancel"), command=self.destroy).pack(side="right")
        self.ok_btn = ttk.Button(btns, text=t("btn_import"), command=self.do_import)
        self.ok_btn.pack(side="right", padx=(0, 6))

        self.reparse()
        self.show()

    # --- parsing / layout ---
    def reparse(self):
        delim = DELIMS[self.delim_labels.index(self.delim_var.get())][1]
        self.rows, _ = core.read_csv_rows(self.text, delim)
        lay = core.detect_layout(self.rows)
        self._busy = True
        self.skip_var.set(lay.skip_top)
        self.header_var.set(lay.has_header)
        self._busy = False
        self._build_columns(lay.columns, set(lay.selected), lay.group_col)
        self._fill_tree()
        self.update_preview()

    def relayout(self):
        """Re-analyze columns when the skip/header settings change (keeps the user's column picks)."""
        if self._busy:
            return
        try:
            skip = max(0, int(self.skip_var.get()))
        except (tk.TclError, ValueError):
            return
        has_header = self.header_var.get()
        prev = {i for i, v in enumerate(self.col_vars) if v.get()}
        cols = core.analyze_columns(self.rows, skip, has_header)
        selected = prev or set(core.auto_select(cols, has_header))
        group = self.group_index()
        if group is None and not prev:
            group = core.detect_group_column(cols, selected, has_header)
        self._build_columns(cols, selected, group)
        self._fill_tree()
        self.update_preview()

    def _build_columns(self, columns, selected, group_col=None):
        for w in self.col_frame.winfo_children():
            w.destroy()
        self.columns = columns
        self.col_vars = []
        self.group_choices = [t("none")]
        for c in columns[:self.MAX_COL_CHECKS]:
            v = tk.BooleanVar(value=c.index in selected)
            self.col_vars.append(v)
            name = c.header or self._sample(c.index)
            label = f"{core.column_letter(c.index)}: {name[:18]}  ({t('kind_' + c.dominant_kind())})"
            ttk.Checkbutton(self.col_frame, text=label, variable=v, command=self.update_preview).grid(
                row=c.index // 3, column=c.index % 3, sticky="w", padx=(0, 18))
            self.group_choices.append(f"{core.column_letter(c.index)}: {name[:18]}")
        if len(columns) > self.MAX_COL_CHECKS:
            ttk.Label(self.col_frame, text=t("csv_too_many_cols", n=self.MAX_COL_CHECKS)).grid(
                row=99, column=0, columnspan=3, sticky="w")
        if not columns:
            ttk.Label(self.col_frame, text=t("csv_no_cols")).grid(row=0, column=0)
            return
        grow = ttk.Frame(self.col_frame)
        grow.grid(row=100, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(grow, text=t("csv_group")).pack(side="left")
        cb = ttk.Combobox(grow, textvariable=self.group_var, values=self.group_choices, width=22,
                          state="readonly")
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
        ttk.Label(grow, text=t("csv_group_hint"), style="Hint.TLabel").pack(side="left")
        ok = group_col is not None and group_col + 1 < len(self.group_choices)
        self.group_var.set(self.group_choices[group_col + 1] if ok else self.group_choices[0])

    def group_index(self):
        v = self.group_var.get()
        if v in self.group_choices[1:]:
            return self.group_choices.index(v) - 1
        return None

    def _sample(self, ci):
        start = self._skip() + (1 if self.header_var.get() else 0)
        for r in self.rows[start:start + 20]:
            if ci < len(r) and r[ci]:
                return t("csv_sample", v=r[ci])
        return t("csv_empty_col")

    def _skip(self):
        try:
            return max(0, int(self.skip_var.get()))
        except (tk.TclError, ValueError):
            return 0

    def _fill_tree(self):
        ncols = max((len(r) for r in self.rows), default=0)
        ids = ["row"] + [f"c{i}" for i in range(ncols)]
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=ids)
        self.tree.heading("row", text=t("csv_row"))
        self.tree.column("row", width=44, stretch=False, anchor="e")
        for i in range(ncols):
            self.tree.heading(f"c{i}", text=core.column_letter(i))
            self.tree.column(f"c{i}", width=120, stretch=True)
        skip, header = self._skip(), self.header_var.get()
        for ri, r in enumerate(self.rows[:self.PREVIEW_ROWS]):
            tag = "skip" if ri < skip else ("header" if header and ri == skip else "")
            self.tree.insert("", "end", values=[ri + 1] + r + [""] * (ncols - len(r)), tags=(tag,))

    # --- result ---
    def selected_columns(self):
        return [i for i, v in enumerate(self.col_vars) if v.get()]

    def update_preview(self):
        if not hasattr(self, "result_list"):
            return
        cols = self.selected_columns()
        for c in self.columns[:self.MAX_COL_CHECKS]:
            self.tree.heading(f"c{c.index}",
                              text=("✔ " if c.index in cols else "") + core.column_letter(c.index))
        exclude = [x for x in self.exclude_var.get().split(",") if x.strip()]
        entries = core.extract_entries(self.rows, self._skip(), self.header_var.get(), cols,
                                       self.drop_num_var.get(), self.drop_head_var.get(), exclude,
                                       self.group_index())
        self.result = [k for k, _ in entries]
        self.groups = {k: g for k, g in entries if g}
        dup = sum(1 for w in self.result if core.key(w) in self.existing)
        n_groups = len(set(self.groups.values()))
        self.count_label.configure(
            text=t("csv_count", n=len(self.result))
            + (t("csv_count_groups", n=n_groups) if n_groups else "")
            + (t("csv_count_dup", n=dup) if dup else ""))
        self.result_list.delete(0, "end")
        for k, g in entries[:2000]:
            self.result_list.insert("end", f"{k}  · {g}" if g else k)
        self.ok_btn.state(["!disabled"] if self.result else ["disabled"])

    def do_import(self):
        if self.result:
            self.on_import(self.result, "CSV", self.groups)
            self.destroy()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.s = self.winfo_fpixels("1i") / 96.0
        self.minsize(int(860 * self.s), int(560 * self.s))
        self.geometry(f"{int(1040 * self.s)}x{int(660 * self.s)}")

        self.store = Store()
        self.sysrand = random.SystemRandom()  # picks the winner (OS randomness)
        self.rng = random.Random()  # reel order
        self.spinning = False
        self.anim = None
        self.last_winner = None
        self.status = ("status_ready", False, {})
        self.auto_exclude = tk.BooleanVar(value=True)
        self.speed_key = "normal"
        self.speed = tk.StringVar()
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *a: self.refresh_lists())
        self.data_file = data_path()

        self._style()
        self._load()
        self._build()
        self.refresh_lists()
        self.rebuild_reel()

        self.bind("<space>", self._key_spin)
        self.bind("<Return>", self._key_spin)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- UI ---
    def _style(self):
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=FONT, size=10)
            except tk.TclError:
                pass
        st = ttk.Style(self)
        st.configure("Count.TLabel", font=(FONT, 10, "bold"))
        st.configure("Hint.TLabel", foreground="#666666")

    def _build(self):
        pad = 10
        top = ttk.Frame(self, padding=(pad, pad, pad, 0))
        top.pack(fill="x")
        ttk.Button(top, text=t("btn_input"), command=self.open_input).pack(side="left")
        ttk.Button(top, text=t("btn_open"), command=self.open_file).pack(side="left", padx=6)
        ttk.Button(top, text=t("btn_lang"), command=self.toggle_lang).pack(side="right")
        ttk.Button(top, text=t("btn_reset"), command=self.reset_all).pack(side="right", padx=6)

        body = ttk.Frame(self, padding=pad)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # left: slot
        left = tk.Frame(body, bg=REEL_BG, padx=int(16 * self.s), pady=int(16 * self.s))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, pad))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        self.result_label = tk.Label(left, bg=REEL_BG, fg=SOFT, font=(FONT, 15, "bold"))
        self.result_label.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        # wrap long winners instead of pushing the window wider
        left.bind("<Configure>", lambda e: self.result_label.configure(
            wraplength=max(100, e.width - int(40 * self.s))))
        self.reel = Reel(left, self.s)
        self.reel.grid(row=1, column=0, sticky="nsew")
        self.spin_btn = tk.Button(left, text="SPIN  (Space)", command=self.spin, font=(FONT, 16, "bold"),
                                  bg=GOLD, fg=REEL_BG, activebackground="#ffd965", activeforeground=REEL_BG,
                                  relief="flat", bd=0, cursor="hand2", pady=int(8 * self.s),
                                  disabledforeground="#7a6a30")
        self.spin_btn.grid(row=2, column=0, sticky="ew", pady=(14, 8))
        opts = tk.Frame(left, bg=REEL_BG)
        opts.grid(row=3, column=0, sticky="ew")
        tk.Checkbutton(opts, text=t("opt_auto_exclude"), variable=self.auto_exclude,
                       command=self.save, bg=REEL_BG, fg=SOFT, selectcolor=REEL_BAND,
                       activebackground=REEL_BG, activeforeground="#ffffff", font=(FONT, 10)).pack(side="left")
        speed_labels = [t("speed_" + k) for k in SPEEDS]
        self.speed.set(t("speed_" + self.speed_key))
        cb = ttk.Combobox(opts, textvariable=self.speed, values=speed_labels, width=7, state="readonly")
        cb.pack(side="right")
        cb.bind("<<ComboboxSelected>>", lambda e: self._speed_changed(speed_labels))
        tk.Label(opts, text=t("opt_speed"), bg=REEL_BG, fg=SOFT, font=(FONT, 10)).pack(side="right", padx=6)
        self.copy_btn = tk.Button(opts, text=t("btn_copy"), command=self.copy_result, font=(FONT, 9),
                                  bg=REEL_BAND, fg=SOFT, relief="flat", bd=0, padx=8,
                                  state="normal" if self.last_winner else "disabled")
        self.copy_btn.pack(side="right", padx=12)

        # right: lists
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(2, weight=3)
        right.rowconfigure(5, weight=2)

        frow = ttk.Frame(right)
        frow.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(frow, text=t("search")).pack(side="left")
        ttk.Entry(frow, textvariable=self.filter_var).pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.cand_label = ttk.Label(right, style="Count.TLabel")
        self.cand_label.grid(row=1, column=0, sticky="w")
        self.excl_label = ttk.Label(right, style="Count.TLabel")
        self.excl_label.grid(row=1, column=1, sticky="w", padx=(8, 0))
        self.cand_list = self._listbox(right, 2, 0, (0, 0))
        self.excl_list = self._listbox(right, 2, 1, (8, 0))
        self.cand_list.bind("<Double-Button-1>", lambda e: self.exclude_selected())
        self.excl_list.bind("<Double-Button-1>", lambda e: self.restore_selected())
        self.cand_list.bind("<Delete>", lambda e: self.delete_selected(self.cand_list))
        self.excl_list.bind("<Delete>", lambda e: self.delete_selected(self.excl_list))

        cbar = ttk.Frame(right)
        cbar.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(cbar, text=t("btn_exclude"), command=self.exclude_selected).pack(side="left")
        ttk.Button(cbar, text=t("btn_delete"),
                   command=lambda: self.delete_selected(self.cand_list)).pack(side="left", padx=4)
        ebar = ttk.Frame(right)
        ebar.grid(row=3, column=1, sticky="ew", pady=(4, 0), padx=(8, 0))
        ttk.Button(ebar, text=t("btn_restore"), command=self.restore_selected).pack(side="left")
        ttk.Button(ebar, text=t("btn_restore_all"), command=self.restore_all).pack(side="left", padx=4)
        ttk.Button(ebar, text=t("btn_delete"), command=lambda: self.delete_selected(self.excl_list)).pack(side="left")
        ttk.Label(right, text=t("hint_lists"), style="Hint.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        hrow = ttk.Frame(right)
        hrow.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(hrow, text=t("history"), style="Count.TLabel").pack(side="left")
        ttk.Button(hrow, text=t("btn_clear_history"), command=self.clear_history).pack(side="right")
        self.hist_list = self._listbox(right, 5, 0, (0, 0), columnspan=2, select="browse")
        self.render_status()

    def _listbox(self, parent, row, col, padx, columnspan=1, select="extended"):
        frm = ttk.Frame(parent)
        frm.grid(row=row, column=col, columnspan=columnspan, sticky="nsew", padx=padx, pady=(4, 0))
        lb = tk.Listbox(frm, selectmode=select, font=(FONT, 10), activestyle="none", exportselection=False,
                        width=1, height=4)
        sb = ttk.Scrollbar(frm, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return lb

    def _speed_changed(self, labels):
        self.speed_key = list(SPEEDS)[labels.index(self.speed.get())]
        self.save()
        self.focus_set()

    def toggle_lang(self):
        if self.spinning:
            return
        i18n.set_lang("ko" if i18n.get_lang() == "en" else "en")
        self.save()
        order, pos = self.reel.order, self.reel.pos
        for w in self.winfo_children():
            w.destroy()
        self._build()
        self.reel.set_order(order, pos=pos)
        self.refresh_lists()

    # --- status line above the reel ---
    def set_status(self, key, gold=False, **kw):
        self.status = (key, gold, kw)
        self.render_status()

    def render_status(self):
        key, gold, kw = self.status
        if key == "status_added":
            source = kw["source"] or t("manual_source")
            text = t(key, source=source, added=kw["added"]) + (t("status_dup", dup=kw["dup"]) if kw["dup"] else "")
        elif key == "status_winner":
            text = t(key, winner=kw["winner"])
            if kw.get("group"):
                text += "\n" + t("status_group", group=kw["group"])
            if kw.get("copied"):
                text += "  " + t("status_copied")
        else:
            text = t(key)
        self.result_label.configure(text=text, fg=GOLD if gold else SOFT)

    # --- lists ---
    def refresh_lists(self):
        q = self.filter_var.get().strip().casefold()
        for lb, items, label, title in ((self.cand_list, self.store.candidates, self.cand_label, t("candidates")),
                                        (self.excl_list, self.store.excluded, self.excl_label, t("excluded"))):
            view = [w for w in items if q in self.store.label(w).casefold()] if q else list(items)
            lb.delete(0, "end")
            for w in view:
                lb.insert("end", self.store.label(w))
            lb.view = view
            label.configure(text=f"{title} ({len(items)})" + (t("search_count", n=len(view)) if q else ""))
        self.hist_list.delete(0, "end")
        for ts, w in reversed(self.store.history):
            self.hist_list.insert("end", f"{ts[5:]}   {w}")
        self.spin_btn.configure(state="normal" if self.store.candidates and not self.spinning else "disabled")

    def _selected(self, lb):
        return [lb.view[i] for i in lb.curselection() if i < len(lb.view)]

    def rebuild_reel(self):
        keep = self.reel.current()
        self.reel.set_order(core.arrange(self.store.candidates, self.rng, time_budget=0.15,
                                         groups=self.store.groups), keep=keep)

    def changed(self, rebuild=True):
        self.refresh_lists()
        if rebuild:
            self.rebuild_reel()
        self.save()

    def add_words(self, words, source, groups=None):
        """source: file name, or None for manual input."""
        if self.spinning:
            return
        added, dup = self.store.add(words, groups)
        self.changed()
        self.set_status("status_added", source=source, added=added, dup=dup)

    def exclude_selected(self):
        if not self.spinning:
            self.store.exclude(self._selected(self.cand_list))
            self.changed()

    def restore_selected(self):
        if not self.spinning:
            self.store.restore(self._selected(self.excl_list))
            self.changed()

    def restore_all(self):
        if not self.spinning and self.store.excluded:
            self.store.restore(list(self.store.excluded))
            self.changed()

    def delete_selected(self, lb):
        words = self._selected(lb)
        if self.spinning or not words:
            return
        if len(words) > 1 and not messagebox.askyesno(APP_NAME, t("confirm_delete", n=len(words)), parent=self):
            return
        self.store.delete(words)
        self.changed()

    def clear_history(self):
        if self.store.history and messagebox.askyesno(APP_NAME, t("confirm_clear_history"), parent=self):
            self.store.history.clear()
            self.changed(rebuild=False)

    def reset_all(self):
        if self.spinning:
            return
        if messagebox.askyesno(APP_NAME, t("confirm_reset"), parent=self):
            self.store = Store()
            self.last_winner = None
            self.set_status("status_ready")
            self.copy_btn.configure(state="disabled")
            self.changed()

    # --- input ---
    def open_input(self):
        if not self.spinning:
            InputDialog(self, self.add_words)

    def open_file(self):
        if self.spinning:
            return
        paths = filedialog.askopenfilenames(
            parent=self, title=t("file_title"),
            filetypes=[(t("ft_keywords"), "*.csv *.txt"), ("CSV", "*.csv"), (t("ft_text"), "*.txt"),
                       (t("ft_all"), "*.*")])
        for path in paths:
            try:
                text, enc = core.read_file_text(path)
            except OSError as e:
                messagebox.showerror(APP_NAME, t("err_open", path=path, err=e), parent=self)
                continue
            name = os.path.basename(path)
            if path.lower().endswith((".csv", ".tsv")):
                dlg = CsvImportDialog(self, path, text, enc, self.store.keys(),
                                      lambda words, src, groups, n=name: self.add_words(words, n, groups))
                self.wait_window(dlg)
            else:
                words = core.parse_txt(text)
                if words:
                    self.add_words(words, name)
                else:
                    messagebox.showinfo(APP_NAME, t("no_keywords_found", name=name), parent=self)

    # --- spin ---
    def _key_spin(self, event):
        # keep the normal behavior in text fields and on buttons that have keyboard focus
        if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text, tk.Spinbox, ttk.Spinbox,
                                     ttk.Button, ttk.Checkbutton, tk.Checkbutton)):
            return
        self.spin()

    def spin(self):
        if self.spinning or not self.store.candidates:
            return
        winner = self.sysrand.choice(self.store.candidates)  # every candidate has the same chance
        self.rebuild_reel()  # fresh random order every spin (similar keywords spread apart)
        order = self.reel.order
        n = len(order)
        p0 = round(self.reel.pos)
        dur = SPEEDS[self.speed_key]
        min_rows = int(11 * dur)
        delta = (order.index(winner) - p0) % n
        dist = delta + n * max(0, math.ceil((min_rows - delta) / n))
        self.anim = (time.perf_counter(), dur, p0, dist, winner)
        self.spinning = True
        self.reel.flash = False
        self.set_status("status_spinning")
        self.copy_btn.configure(state="disabled")
        self.refresh_lists()
        self._tick()

    def _tick(self):
        t0, dur, p0, dist, winner = self.anim
        u = min(1.0, (time.perf_counter() - t0) / dur)
        if u >= 1.0:
            self.reel.pos = float(p0 + dist)
            self.reel.redraw()
            self._finish(winner)
            return
        pos = p0 + dist * (1 - (1 - u) ** 4)  # ease-out
        if u > 0.8:  # overshoot slightly and settle back just before stopping
            pos += 0.22 * math.sin(math.pi * (u - 0.8) / 0.2)
        self.reel.pos = pos
        self.reel.redraw()
        self.after(12, self._tick)

    def _finish(self, winner):
        self.spinning = False
        self.last_winner = winner
        self.store.history.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S"), winner))
        if self.auto_exclude.get():
            self.store.exclude([winner])
        self.set_status("status_winner", gold=True, winner=winner, group=self.store.groups.get(winner))
        self.copy_btn.configure(state="normal")
        self.changed(rebuild=False)  # keep the winner visible in the middle of the reel
        self._flash(6)

    def _flash(self, n):
        if n <= 0 or self.spinning:
            self.reel.flash = False
            self.reel.redraw()
            return
        self.reel.flash = not self.reel.flash
        self.reel.redraw()
        self.after(140, self._flash, n - 1)

    def copy_result(self):
        if self.last_winner:
            self.clipboard_clear()
            self.clipboard_append(self.last_winner)
            key, gold, kw = self.status
            if key == "status_winner":
                self.set_status(key, gold, **dict(kw, copied=True))

    # --- persistence ---
    def _load(self):
        try:
            with open(self.data_file, encoding="utf-8") as fh:
                d = json.load(fh)
            self.store.load(d)
            self.auto_exclude.set(bool(d.get("auto_exclude", True)))
            speed = LEGACY_SPEEDS.get(d.get("speed"), d.get("speed"))
            if speed in SPEEDS:
                self.speed_key = speed
            i18n.set_lang(d.get("lang", i18n.DEFAULT_LANG))
        except (OSError, ValueError, AttributeError):
            pass

    def save(self):
        d = self.store.to_dict()
        d["auto_exclude"] = self.auto_exclude.get()
        d["speed"] = self.speed_key
        d["lang"] = i18n.get_lang()
        try:
            tmp = self.data_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.data_file)
        except OSError:
            pass

    def _on_close(self):
        self.save()  # closing mid-spin discards that spin
        self.destroy()


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
