"""
DataGraph.py — Publication-quality matplotlib styling
=====================================================

Usage
-----
    import DataGraph as dg
    dg.set_style(figure_size=(3.5, 2.5))
    palette = dg.get_palette()

    fig, ax = plt.subplots()
    ax.plot(x, y, color=palette["blue"])
    plt.show()

    # Progress bar (GitHub-safe in Jupyter)
    for x in dg.track(range(1000), desc="Training"):
        dg.sleep(0.001)

Version history
---------------
    1.0.0  (10 Feb 2026)  Initial release.
    1.1.0  (10 Mar 2026)  TableMaker for rich tables.
    1.2.0  (13 Mar 2026)  Auto-scaling; Palette dual-access.
    1.3.0  (23 Mar 2026)  Paul Tol / IBM palettes.
    2.0.0  (21 Apr 2026)  Fixed-fraction subplot layout;
                           fixed_frame() context manager;
                           internal helpers prefixed with _.
                           Public helper aliases; Palette repr;
                           lazy rich import; Academic monochrome table theme;
                           removed unused os import.
    3.0.0  (19 May 2026)  ProgressBar + track() — static-HTML progress bar
                           in the TableMaker style. Renders as plain HTML in
                           Jupyter so the final state survives GitHub's
                           notebook renderer (unlike tqdm.auto's ipywidgets).
                           Throttled refresh, ANSI fallback for terminals,
                           iterator + context-manager interface.
    3.0.1  (19 May 2026)  Bind dg.sleep to time.sleep (was declared in
                           __all__ but never assigned, causing
                           AttributeError on import-time *-imports and on
                           direct attribute access).
    3.1.0  (16 Jul 2026)  Bug-fix release:
                           - TableMaker._render_html now HTML-escapes the
                             title, column headers, and every cell value
                             (previously unescaped, so "<", ">", "&" in
                             data corrupted the markup).
                           - Header <th> cells are now wrapped in a <tr>
                             (previously emitted directly inside <thead>,
                             which is invalid HTML).
                           - rich is now genuinely lazily imported inside
                             TableMaker._render_text, matching the 2.0.0
                             changelog claim; it is no longer a hard
                             dependency for users who only need styling.
                           - TableMaker._render_text now wraps every cell
                             in rich.text.Text so literal "[...]" in data
                             (e.g. bracketed units) can never be
                             misinterpreted as Rich console markup.
                           - Console(force_terminal=...) now reflects the
                             real stdout tty state, so terminal colour is
                             preserved instead of being unconditionally
                             stripped by the StringIO buffering trick.
                           - TableMaker(mode=...) now validates against
                             {"static", "live", "dynamic"} and raises
                             ValueError on an unrecognised mode instead of
                             silently behaving like "static".
                           - _resolve_palette now warns (UserWarning) when
                             falling back to the default palette on an
                             unrecognised name, instead of failing silently.
                           - ProgressBar._render_text now clamps the
                             completion fraction to [0, 1] before computing
                             the filled-bar width, matching the clamp
                             already present in _render_html.
"""

__version__ = "3.1.0"
__date__ = "16 Jul 2026"

__all__ = [
    # ── Constants ──
    "EPS",
    # ── Palette ──
    "Palette",
    "get_palette",
    "build_color_map",
    # ── Style ──
    "set_style",
    "reset_style",
    "fixed_frame",
    # ── Helpers ──
    "finalize",
    "style_colorbar",
    "annotate_panels",
    "enable_minor_ticks",
    "apply_grid",
    # ── Table ──
    "TableMaker",
    # ── Progress ──
    "ProgressBar",
    "track",
    "sleep",
    # ── Info ──
    "info",
]

# ── Imports ──────────────────────────────────────────────────────────

import sys
import time
import html as _html
import warnings
from contextlib import contextmanager

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from io import StringIO

# NOTE: rich is intentionally NOT imported at module level. TableMaker is
# the only feature that needs it, and its renderers import rich lazily
# (see TableMaker._render_text), so set_style()/get_palette()/etc. work
# even if rich isn't installed.

# ── Constants ────────────────────────────────────────────────────────

EPS = np.finfo(np.float64).eps

_REF_WIDTH = 6.0
_SCALE_EXPONENT = 0.5

# Default subplot fractions (axes position within figure)
_DEFAULT_SUBPLOT = {
    "left":   0.18,
    "bottom": 0.20,
    "right":  0.95,
    "top":    0.93,
}

# ── Re-export: stdlib sleep ─────────────────────────────────────────
# Bound here (not via tqdm.auto, which depends on ipywidgets and is on
# track to break in future Jupyter releases). Pure stdlib, zero risk.
sleep = time.sleep

# ── Colour Palettes ─────────────────────────────────────────────────

_PALETTES = {
    "tableau10": {
        "colors": [
            "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
            "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
        ],
        "names": [
            "blue", "orange", "red", "teal", "green",
            "yellow", "purple", "pink", "brown", "grey",
        ],
    },
    "okabe-ito": {
        "colors": [
            "#0072B2", "#E69F00", "#D55E00", "#009E73",
            "#56B4E9", "#F0E442", "#CC79A7", "#000000",
        ],
        "names": [
            "blue", "orange", "red", "green",
            "cyan", "yellow", "purple", "black",
        ],
    },
    "paul-tol-vibrant": {
        "colors": [
            "#0077BB", "#33BBEE", "#009988", "#EE7733",
            "#CC3311", "#EE3377", "#BBBBBB",
        ],
        "names": [
            "blue", "cyan", "teal", "orange",
            "red", "magenta", "grey",
        ],
    },
    "paul-tol-bright": {
        "colors": [
            "#4477AA", "#EE6677", "#228833", "#CCBB44",
            "#66CCEE", "#AA3377", "#BBBBBB",
        ],
        "names": [
            "blue", "red", "green", "yellow",
            "cyan", "purple", "grey",
        ],
    },
    "paul-tol-muted": {
        "colors": [
            "#332288", "#88CCEE", "#44AA99", "#117733",
            "#999933", "#DDCC77", "#CC6677", "#882255", "#AA4499",
        ],
        "names": [
            "indigo", "cyan", "teal", "green",
            "olive", "sand", "rose", "wine", "purple",
        ],
    },
    "ibm": {
        "colors": ["#648FFF", "#785EF0", "#DC267F", "#FE6100", "#FFB000"],
        "names": ["blue", "indigo", "magenta", "orange", "gold"],
    },
}


class Palette:
    """Colour palette with both name-based and index-based access."""

    def __init__(self, names, colors):
        self._names = list(names)
        self._colors = list(colors)
        self._map = dict(zip(self._names, self._colors))

    def __repr__(self):
        pairs = ", ".join(f"{n}={c}" for n, c in zip(self._names, self._colors))
        return f"Palette({pairs})"

    def __getitem__(self, key):
        if isinstance(key, (int, np.integer)):
            return self._colors[key % len(self._colors)]
        if isinstance(key, slice):
            return self._colors[key]
        if isinstance(key, str):
            return self._map[key.lower()]
        raise KeyError(key)

    def __contains__(self, key):
        if isinstance(key, str):
            return key.lower() in self._map
        if isinstance(key, (int, np.integer)):
            return -len(self._colors) <= key < len(self._colors)
        return False

    def __iter__(self):
        return iter(self._colors)

    def __len__(self):
        return len(self._colors)

    def keys(self):
        return self._map.keys()

    def values(self):
        return self._map.values()

    def items(self):
        return self._map.items()


# ── Internal Helpers ─────────────────────────────────────────────────

def _is_jupyter():
    """Detect whether code is running inside a Jupyter / IPython kernel."""
    return "ipykernel" in sys.modules


def _compute_scale(fig_width, exponent=_SCALE_EXPONENT):
    raw = (fig_width / _REF_WIDTH) ** exponent
    return float(np.clip(raw, 0.55, 2.2))


def _resolve_palette(name):
    p = str(name).lower()
    if "vibrant" in p:                return "paul-tol-vibrant"
    if "bright" in p:                 return "paul-tol-bright"
    if "muted" in p:                  return "paul-tol-muted"
    if "tol" in p or "paul" in p:     return "paul-tol-vibrant"
    if "tab" in p or "tableau" in p:  return "tableau10"
    if "ibm" in p:                    return "ibm"
    if "okabe" in p or "ito" in p:    return "okabe-ito"
    warnings.warn(
        f"Unrecognised palette name {name!r}; falling back to 'okabe-ito'. "
        f"Known palettes: {sorted(_PALETTES)}",
        UserWarning,
        stacklevel=3,
    )
    return "okabe-ito"  # Default palette


class _SkipZeroFormatter(mticker.ScalarFormatter):
    def __call__(self, x, pos=None):
        return "" if np.isclose(x, 0.0) else super().__call__(x, pos)


def _to_axes_list(ax):
    if ax is None:
        return [plt.gca()]
    if isinstance(ax, np.ndarray):
        return ax.ravel().tolist()
    if hasattr(ax, "__iter__") and not hasattr(ax, "plot"):
        return list(ax)
    return [ax]


def _fix_origin_overlap(ax=None, keep="x"):
    if ax is None:
        ax = plt.gca()
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    if not (xlim[0] <= 0 <= xlim[1] and ylim[0] <= 0 <= ylim[1]):
        return
    target = ax.yaxis if keep == "x" else ax.xaxis
    current = target.get_major_formatter()
    if isinstance(current, (mticker.ScalarFormatter, _SkipZeroFormatter)):
        fmt = _SkipZeroFormatter()
        try:
            fmt.set_useOffset(current.get_useOffset())
            fmt.set_useMathText(current.get_useMathText())
        except AttributeError:
            pass
        target.set_major_formatter(fmt)


def _apply_grid(ax=None, axis="both"):
    if ax is None:
        ax = plt.gca()
    ax.grid(True, which="major", axis=axis,
            linestyle=":", color="black", alpha=0.7)
    ax.set_axisbelow(True)


def _fix_legend_frame(ax=None):
    if ax is None:
        ax = plt.gca()
    leg = ax.get_legend()
    if leg is not None:
        frame = leg.get_frame()
        frame.set_linewidth(plt.rcParams.get("axes.linewidth", 1.2))
        frame.set_edgecolor(plt.rcParams.get("legend.edgecolor", "black"))


def _enable_minor_ticks(ax=None, x=True, y=True):
    if ax is None:
        ax = plt.gca()
    if x:
        ax.xaxis.set_minor_locator(mticker.AutoMinorLocator())
    if y:
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    lw = plt.rcParams.get("xtick.major.width", 1.5) * 0.6
    sz = plt.rcParams.get("xtick.major.size", 8) * 0.5
    ax.tick_params(which="minor", direction="out",
                   length=sz, width=lw, top=True, right=True)


def _style_colorbar(cb, label=None):
    lw = plt.rcParams.get("axes.linewidth", 2.0)
    cb.outline.set_linewidth(lw)
    cb.outline.set_edgecolor("black")
    cb.ax.tick_params(
        direction="out",
        width=plt.rcParams.get("xtick.major.width", lw),
        length=plt.rcParams.get("xtick.major.size", 8) * 0.7,
    )
    if label is not None:
        cb.set_label(label)


def _annotate_panels(axes, labels=None, loc="upper left",
                     offset=None, fontsize=None, fontweight="bold"):
    axes = _to_axes_list(axes)
    if labels is None:
        labels = [f"({chr(97 + i)})" for i in range(len(axes))]
    if fontsize is None:
        fontsize = plt.rcParams["font.size"]
    if offset is not None:
        ox, oy = offset
    elif "right" in loc:
        ox, oy = 0.94, 0.93
    else:
        ox, oy = 0.06, 0.93
    ha = "right" if "right" in loc else "left"
    for a, lbl in zip(axes, labels):
        a.text(ox, oy, lbl, transform=a.transAxes,
               fontsize=fontsize, fontweight=fontweight, va="top", ha=ha)


def _finalize(ax=None, fix_origin=True, keep="x",
              grid=False, minor_ticks=False):
    for a in _to_axes_list(ax):
        if fix_origin:
            _fix_origin_overlap(a, keep=keep)
        _fix_legend_frame(a)
        if grid:
            _apply_grid(a)
        if minor_ticks:
            _enable_minor_ticks(a)


# ── Public Aliases for Helpers ───────────────────────────────────────

finalize           = _finalize
style_colorbar     = _style_colorbar
annotate_panels    = _annotate_panels
enable_minor_ticks = _enable_minor_ticks
apply_grid         = _apply_grid


# ── Public API ───────────────────────────────────────────────────────

def info():
    """Print version and dependency info."""
    text = (
        f"DataGraph.py  v{__version__}  ({__date__})\n"
        f"  matplotlib  {plt.matplotlib.__version__}\n"
        f"  numpy       {np.__version__}"
    )
    print(text)
    return text


def get_palette(palette="okabe-ito", n=None):
    """Return a Palette object. Supports fuzzy name matching."""
    key = _resolve_palette(palette)
    entry = _PALETTES[key]
    limit = len(entry["colors"]) if n is None else min(n, len(entry["colors"]))
    return Palette(entry["names"][:limit], entry["colors"][:limit])


def build_color_map(labels, palette="okabe-ito"):
    """Map unique labels to palette colours."""
    pal = get_palette(palette=palette)
    return {lab: pal[i] for i, lab in enumerate(labels)}


def set_style(
    base_fontsize=12.5,
    linewidth=1.2,
    figure_size=(3.5, 2.5),
    subplot=None,
    use_tex=False,
    auto_scale=True,
    scale_exponent=_SCALE_EXPONENT,
    palette="okabe-ito",
):
    """
    One-call global setup.

    figure_size is the primary parameter.  Subplot fractions are
    fixed so the inner axes box occupies the same region regardless
    of tick-label content.  autolayout is OFF; savefig bbox="tight"
    acts as a safety net on export.
    """
    sp = {**_DEFAULT_SUBPLOT, **(subplot or {})}
    s = _compute_scale(figure_size[0], scale_exponent) if auto_scale else 1.0

    fs    = base_fontsize * s
    lw    = linewidth * s
    elw   = lw * 0.6
    ms    = 9.0 * s
    major = 5.0 * s
    minor = 3.0 * s

    plt.rcParams.update({
        # ── Font ──
        "font.family":           "serif",
        "font.serif":            ["Times New Roman", "Times", "DejaVu Serif"],
        "text.latex.preamble":   r"\usepackage{newtxtext,newtxmath}",
        "font.size":             fs - 2 * s,
        "axes.titlesize":        fs,
        "axes.labelsize":        fs - 1 * s,
        "xtick.labelsize":       fs - 2 * s,
        "ytick.labelsize":       fs - 2 * s,

        # ── Figure ──
        "figure.figsize":        figure_size,
        "figure.dpi":            150,
        "figure.autolayout":     False,
        "savefig.dpi":           300,
        "savefig.bbox":          "tight",
        "pdf.fonttype":          42,
        "ps.fonttype":           42,

        # ── Subplot position (fixed fractions) ──
        "figure.subplot.left":   sp["left"],
        "figure.subplot.bottom": sp["bottom"],
        "figure.subplot.right":  sp["right"],
        "figure.subplot.top":    sp["top"],

        # ── Axes ──
        "axes.linewidth":        lw,
        "axes.spines.top":       True,
        "axes.spines.right":     True,
        "axes.labelpad":         6.0 * s,
        "axes.xmargin":          0.03,
        "axes.ymargin":          0.03,
        "axes.titlepad":         13.0 * s,
        "axes.formatter.useoffset":    False,
        "axes.formatter.use_mathtext": True,
        "axes.formatter.limits":       [-4, 5],

        # ── Ticks ──
        "xtick.direction":       "out",
        "ytick.direction":       "out",
        "xtick.major.size":      major,
        "ytick.major.size":      major,
        "xtick.minor.size":      minor,
        "ytick.minor.size":      minor,
        "xtick.major.width":     lw * 0.8,
        "ytick.major.width":     lw * 0.8,
        "xtick.minor.visible":   False,
        "ytick.minor.visible":   False,
        "xtick.major.pad":       4.0 * s,
        "ytick.major.pad":       4.0 * s,

        # ── Lines & Markers ──
        "lines.linewidth":       lw,
        "lines.markersize":      ms,
        "lines.markeredgewidth": elw,
        "lines.markeredgecolor": "black",

        # ── Patches & Scatter ──
        "scatter.edgecolors":    "black",
        "patch.edgecolor":       "black",
        "patch.linewidth":       elw,
        "patch.force_edgecolor": True,

        # ── Legend ──
        "legend.fontsize":       fs - 4 * s,
        "legend.frameon":        True,
        "legend.framealpha":     1.0,
        "legend.facecolor":      "white",
        "legend.edgecolor":      "black",
        "legend.fancybox":       False,
        "legend.handlelength":   1.5,

        # ── Text & Math ──
        "text.usetex":           use_tex,
        "mathtext.fontset":      "stix",

        # ── Grid ──
        "axes.grid":             False,
        "grid.linestyle":        "--",
        "grid.color":            "black",
        "grid.alpha":            0.8,
        "grid.linewidth":        lw * 0.67,
        "axes.axisbelow":        True,
    })

    plt.rcParams["axes.prop_cycle"] = plt.cycler(
        color=list(get_palette(palette))
    )


def reset_style():
    """Restore matplotlib defaults."""
    plt.rcdefaults()


@contextmanager
def fixed_frame(figure_size=None, subplot=None, **ax_kw):
    """
    Context manager for per-figure size/layout override.
    Falls back to current rcParams when arguments are None.
    """
    fs = figure_size or plt.rcParams["figure.figsize"]
    sp = {**_DEFAULT_SUBPLOT, **(subplot or {})}
    rect = [sp["left"], sp["bottom"],
            sp["right"] - sp["left"], sp["top"] - sp["bottom"]]

    prev = plt.rcParams.get("figure.autolayout", False)
    plt.rcParams["figure.autolayout"] = False

    fig = plt.figure(figsize=fs)
    ax = fig.add_axes(rect, **ax_kw)

    try:
        yield fig, ax
    finally:
        plt.rcParams["figure.autolayout"] = prev


# ── TableMaker ───────────────────────────────────────────────────────

_TABLE_MODES = ("static", "live", "dynamic")


class TableMaker:
    """Table for console / Jupyter with optional live updates."""

    def __init__(self, title="Analysis", columns=None, mode="static"):
        if mode not in _TABLE_MODES:
            raise ValueError(
                f"Unknown mode {mode!r}; expected one of {_TABLE_MODES}."
            )
        self.title = title
        self.columns = columns or ["Parameter", "Value", "Unit"]
        self.data = []
        self.mode = mode
        self._jupyter = _is_jupyter()
        self._prev_lines = 0
        self._handle = None

    # ── Renderers ──

    def _render_html(self):
        """
        Academic-style (Booktabs) table.
        Works perfectly in both Light and Dark modes using 'currentColor'.
        All text content is HTML-escaped to survive arbitrary data.
        """
        # ── Design Constants ──
        LINE_COLOR = "currentColor"
        TEXT_COLOR = "currentColor"
        FONT_FAMILY = "'Times New Roman', Times, serif"

        esc = _html.escape

        # Header cells (wrapped in a single <tr>)
        hdr_cells = ""
        for i, c in enumerate(self.columns):
            align = "left" if i == 0 else "right"
            hdr_cells += (
                f'<th style="padding:10px 14px; text-align:{align}; '
                f'font-weight:bold; color:{TEXT_COLOR}; '
                f'border-top:2.5px solid {LINE_COLOR}; '
                f'border-bottom:1.2px solid {LINE_COLOR}; '
                f'font-size:14px; background:none">{esc(str(c))}</th>'
            )
        hdr = f'<tr>{hdr_cells}</tr>'

        # Body rows
        body = ""
        for r, row in enumerate(self.data):
            cells = ""
            is_last = (r == len(self.data) - 1)
            bottom_border = f"2.5px solid {LINE_COLOR}" if is_last else "none"

            for i, c in enumerate(row):
                align = "left" if i == 0 else "right"
                cells += (
                    f'<td style="padding:8px 14px; text-align:{align}; '
                    f'font-size:13px; color:{TEXT_COLOR}; '
                    f'border-bottom:{bottom_border}; background:none">'
                    f'{esc(str(c))}</td>'
                )
            body += f'<tr>{cells}</tr>'

        return (
            f'<div style="margin:15px 0; display:inline-block; background:none">'
            f'<div style="font-family:{FONT_FAMILY}; font-weight:bold; color:{TEXT_COLOR}; '
            f'font-size:14px; margin-bottom:10px; text-align:left">{esc(str(self.title))}</div>'
            f'<table style="border-collapse:collapse; font-family:{FONT_FAMILY}; '
            f'border:none; line-height:1.5; color:{TEXT_COLOR}; background:none">'
            f'<thead>{hdr}</thead>'
            f'<tbody>{body}</tbody></table></div>'
        )

    def _render_text(self):
        """Rich-formatted text for terminal only. rich is imported lazily
        so it is not a hard dependency for users who never call display()
        or add_row() in live/dynamic mode."""
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text

        buf = StringIO()
        # Text objects are always literal — square brackets in data can
        # never be misread as Rich console markup (e.g. "[phi=0.4]").
        t = Table(title=Text(str(self.title)))
        for i, col in enumerate(self.columns):
            t.add_column(Text(str(col)), justify="left" if i == 0 else "right")
        for row in self.data:
            t.add_row(*[Text(str(v)) for v in row])

        Console(
            file=buf,
            force_jupyter=False,
            force_terminal=sys.stdout.isatty(),
            width=120,
        ).print(t)
        return buf.getvalue()

    # ── Row management ──

    def add_row(self, *values):
        self.data.append([str(v) for v in values])
        if self.mode in ("live", "dynamic"):
            self._update()

    # ── Update logic ──

    def _update(self):
        if self._jupyter:
            self._update_jupyter()
        else:
            self._update_terminal()

    def _update_terminal(self):
        if self._prev_lines > 0:
            sys.stdout.write(f"\033[{self._prev_lines}A\033[J")
        text = self._render_text()
        sys.stdout.write(text)
        sys.stdout.flush()
        self._prev_lines = text.count("\n")

    def _update_jupyter(self):
        from IPython.display import display, HTML
        html = HTML(self._render_html())
        if self._handle is None:
            self._handle = display(html, display_id=True)
        else:
            self._handle.update(html)

    # ── Static display ──

    def display(self):
        if self._jupyter:
            from IPython.display import display as ipy_display, HTML
            ipy_display(HTML(self._render_html()))
        else:
            print(self._render_text(), end="")


# ── ProgressBar ──────────────────────────────────────────────────────

class ProgressBar:
    """
    Static-HTML progress bar in the TableMaker style.

    Unlike ``tqdm.auto`` (which uses ipywidgets), this renders as plain
    HTML in Jupyter via ``display(..., display_id=True)`` + ``.update()``.
    The final state is therefore preserved as ``text/html`` cell output
    when the notebook is committed to GitHub, where it renders as a
    completed (frozen-at-100 %) progress bar instead of an empty widget.

    Parameters
    ----------
    iterable : iterable, optional
        Wrap an iterable for tqdm-style usage:
        ``for x in ProgressBar(range(N), desc="..."):``.
    total : int, optional
        Total number of iterations.  Inferred from ``len(iterable)`` if
        omitted.  When unknown, an indeterminate bar is shown.
    desc : str, optional
        Prefix label.
    width : int, optional
        Number of characters in the terminal-mode bar.
    mininterval : float, optional
        Minimum seconds between visual refreshes.  Essential for tight
        loops — without it, fast iteration is bottlenecked by HTML
        rendering rather than the actual workload.

    Examples
    --------
    >>> for x in dg.track(range(1000), desc="Training"):
    ...     do_work(x)

    >>> with dg.ProgressBar(total=N, desc="Sweep") as pb:
    ...     for i in range(N):
    ...         compute()
    ...         pb.update()
    """

    # ── Design constants (match TableMaker vibe) ──
    _FONT = "'Times New Roman', Times, serif"
    _BAR_PX = 260

    def __init__(self, iterable=None, total=None, desc="",
                 width=40, mininterval=0.1):
        self.iterable = iterable
        if total is None and iterable is not None:
            try:
                total = len(iterable)
            except TypeError:
                total = None
        self.total = total
        self.desc = desc
        self.width = width
        self.mininterval = mininterval

        self.n = 0
        self._start = None
        self._last = 0.0
        self._handle = None
        self._jupyter = _is_jupyter()
        self._closed = False

    # ── Formatting helpers ──

    @staticmethod
    def _fmt_time(s):
        if s is None or not np.isfinite(s):
            return "?"
        s = int(s)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"

    def _stats(self):
        elapsed = time.monotonic() - self._start if self._start else 0.0
        rate = self.n / elapsed if elapsed > 0 else 0.0
        eta = (self.total - self.n) / rate if (self.total and rate > 0) else None
        frac = self.n / self.total if self.total else 0.0
        return elapsed, rate, eta, frac

    # ── Renderers ──

    def _render_html(self):
        elapsed, rate, eta, frac = self._stats()

        if self.total:
            pct = max(0.0, min(100.0, frac * 100))
            bar = (
                f'<span style="display:inline-block; width:{self._BAR_PX}px; '
                f'height:12px; border:1.2px solid currentColor; '
                f'vertical-align:middle; margin:0 10px; background:none; '
                f'box-sizing:border-box">'
                f'<span style="display:block; width:{pct:.2f}%; height:100%; '
                f'background:currentColor; opacity:0.85"></span></span>'
            )
            label = f"{pct:5.1f}%"
            stats = (
                f"{self.n}/{self.total} "
                f"[{self._fmt_time(elapsed)}&lt;{self._fmt_time(eta)}, "
                f"{rate:.2f} it/s]"
            )
        else:
            bar = (
                f'<span style="display:inline-block; width:{self._BAR_PX}px; '
                f'text-align:center; margin:0 10px; vertical-align:middle; '
                f'opacity:0.7">·  ·  ·</span>'
            )
            label = f"{self.n}"
            stats = f"[{self._fmt_time(elapsed)}, {rate:.2f} it/s]"

        desc = (
            f'<span style="font-weight:bold">{_html.escape(self.desc)}:</span> '
            if self.desc else ''
        )

        return (
            f'<div style="font-family:{self._FONT}; color:currentColor; '
            f'font-size:13px; margin:6px 0; line-height:1.6; background:none">'
            f'{desc}'
            f'<span style="display:inline-block; min-width:48px; '
            f'text-align:right">{label}</span>'
            f'{bar}'
            f'<span style="font-size:12px">{stats}</span>'
            f'</div>'
        )

    def _render_text(self):
        elapsed, rate, eta, frac = self._stats()
        prefix = f"{self.desc}: " if self.desc else ""
        if self.total:
            frac_clamped = max(0.0, min(1.0, frac))
            filled = int(self.width * frac_clamped)
            bar = "█" * filled + "·" * (self.width - filled)
            pct = frac_clamped * 100
            return (
                f"{prefix}{pct:5.1f}% |{bar}| "
                f"{self.n}/{self.total} "
                f"[{self._fmt_time(elapsed)}<{self._fmt_time(eta)}, "
                f"{rate:.2f} it/s]"
            )
        return (
            f"{prefix}{self.n} "
            f"[{self._fmt_time(elapsed)}, {rate:.2f} it/s]"
        )

    # ── Refresh ──

    def _refresh(self, force=False):
        now = time.monotonic()
        if not force and (now - self._last) < self.mininterval:
            return
        self._last = now

        if self._jupyter:
            from IPython.display import display, HTML
            html = HTML(self._render_html())
            if self._handle is None:
                self._handle = display(html, display_id=True)
            else:
                self._handle.update(html)
        else:
            sys.stdout.write("\r\033[K" + self._render_text())
            sys.stdout.flush()

    # ── Public API ──

    def update(self, n=1):
        """Advance the counter by ``n`` and refresh if throttled interval has elapsed."""
        if self._start is None:
            self._start = time.monotonic()
        self.n += n
        is_done = self.total is not None and self.n >= self.total
        self._refresh(force=is_done)

    def set_description(self, desc):
        """Change the prefix label and force a refresh."""
        self.desc = desc
        self._refresh(force=True)

    def close(self):
        """Force a final render so GitHub gets the completed bar in the cell output."""
        if self._closed:
            return
        self._refresh(force=True)
        if not self._jupyter:
            sys.stdout.write("\n")
            sys.stdout.flush()
        self._closed = True

    # ── Iterator + context manager ──

    def __iter__(self):
        if self.iterable is None:
            raise TypeError("ProgressBar has no iterable; use update() instead.")
        if self._start is None:
            self._start = time.monotonic()
        self._refresh(force=True)
        try:
            for item in self.iterable:
                yield item
                self.update(1)
        finally:
            self.close()

    def __enter__(self):
        if self._start is None:
            self._start = time.monotonic()
        self._refresh(force=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def track(iterable=None, **kwargs):
    """tqdm-style convenience wrapper around :class:`ProgressBar`."""
    return ProgressBar(iterable=iterable, **kwargs)
