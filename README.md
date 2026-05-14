# DataGraph

**Publication-quality matplotlib styling for Academic Research.**

DataGraph provides a streamlined interface for generating figures that meet the rigorous standards of scientific journals. It handles font scaling, consistent subplot positioning, and colour-blind friendly palettes with minimal boilerplate.

---

## Key Features

* **Fixed-Fraction Layout**: Prevents axes jumping between figures by enforcing consistent subplot dimensions.
* **Automatic Scaling**: Adjusts font sizes, line widths, and tick marks based on the physical figure width.
* **Academic Palettes**: Built-in support for Okabe-Ito, Paul Tol (Vibrant, Muted, Bright), and IBM palettes.
* **TableMaker**: Renders LaTeX-style "booktabs" tables directly in Jupyter notebooks or the terminal.
* **Context Management**: Use `fixed_frame` for one-off figures with specific dimensions without affecting global settings.

## Installation

Deployment of the library requires a direct installation from the remote repository; this ensures the environment resolves all scientific dependencies during the build process. Users execute the following command to target the specific subfolder containing the package manifest; this syntax directs the installer to the correct build instructions:

```bash
pip install "git+https://github.com/boss507104/DataGraph.git#subdirectory=DataGraph"

```

The inclusion of a `pyproject.toml` file enables the standard Python package manager to identify the source code; this eliminates manual configuration of the local search path. Developers may also install the package from a local directory by navigating to the relevant folder and invoking the installer:

```bash
pip install .

```

## Quick Start

```python
import DataGraph as dg
import matplotlib.pyplot as plt
import numpy as np

# 1. Global setup
dg.set_style(figure_size=(3.5, 2.5), palette="okabe-ito")

# 2. Get the palette
colors = dg.get_palette()

# 3. Plotting
x = np.linspace(0, 10, 100)
fig, ax = plt.subplots()

ax.plot(x, np.sin(x), color=colors['blue'], label='Signal A')
ax.plot(x, np.cos(x), color=colors['orange'], label='Signal B')

ax.set_xlabel('Time (s)')
ax.set_ylabel('Amplitude (V)')
ax.legend()

# 4. Finalise (handles legend borders and origin overlaps)
dg.finalize(ax)
plt.show()


```

## Core Components

### 1. Global Styling (`set_style`)

Configures `plt.rcParams` for publication. Unlike standard matplotlib behaviour, it disables `autolayout` to ensure that labels do not shift the axes box. It defaults to a Times-style serif font.

```python
dg.set_style(
    base_fontsize=12.5,
    linewidth=1.2,
    figure_size=(3.5, 2.5),
    use_tex=False
)


```

### 2. Colour Palettes (`Palette`)

Access colours by name or index. The library supports fuzzy matching for palette names.

* `okabe-ito` (Default)
* `paul-tol-vibrant` | `bright` | `muted`
* `ibm`
* `tableau10`

```python
p = dg.get_palette("vibrant")
color = p['red']    # Name access
color = p[0]        # Index access (wraps around)


```

### 3. Layout Control (`fixed_frame`)

A context manager for creating figures with precise axes placement.

```python
with dg.fixed_frame(figure_size=(5, 4)) as (fig, ax):
    ax.scatter(data_x, data_y)
    # The axes position is determined by internal fractions,
    # ensuring consistent whitespace across different plots.


```

### 4. TableMaker

Create professional tables for results analysis. In Jupyter, it renders a monochrome theme inspired by academic journals.

```python
table = dg.TableMaker(title="Performance Metrics", columns=["Metric", "Result"])
table.add_row("R-Squared", "0.9942")
table.add_row("RMSE", "0.021")
table.display()


```

## API Reference

| Function / Class | Description |
| --- | --- |
| `set_style(...)` | Initialises global matplotlib parameters.

 |
| `get_palette(name)` | Returns a `Palette` object with fuzzy name matching.

 |
| `finalize(ax)` | Polishes the plot (legend frames, grid, minor ticks).

 |
| `fixed_frame(...)` | Context manager for isolated figure styling.

 |
| `annotate_panels(...)` | Automatically adds (a), (b), (c) labels to subplots.

 |
| `TableMaker(...)` | Renders academic-style tables in console or Jupyter.

 |

## Version History

* **v2.0.0 (21 Apr 2026)**: Fixed-fraction subplot layout; academic monochrome table theme; `fixed_frame` context manager.


* **v1.3.0 (23 Mar 2026)**: Added Paul Tol and IBM palettes.


* **v1.2.0 (13 Mar 2026)**: Implemented auto-scaling and dual-access palettes.


* **v1.0.0 (10 Feb 2026)**: Initial release.



---

*Created by DataGraph.py Utility*
