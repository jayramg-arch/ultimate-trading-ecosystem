# 🔄 RRG Studio — Standalone Strike.Money Cockpit

A dedicated, isolated Relative Rotation Graph (RRG) project decoupled from the Web Commander. 

Use this environment for rapid experimentation, algorithmic finetuning, watchlist testing, and interactive analysis without risking any disruption to Web Commander.

---

## 🚀 How to Launch

### Option 1: One-Click Batch Launcher
Double click:
```cmd
LAUNCH_RRG_STUDIO.bat
```
*(Automatically binds to dedicated port `http://localhost:8502` so it runs side-by-side with Web Commander on `8501`).*

### Option 2: CLI Command
```bash
streamlit run rrg_studio/app.py --server.port=8502
```

---

## 📦 Project Architecture

```
rrg_studio/
├── app.py                  # Standalone Streamlit UI with Strike.Money 2-column layout
├── rrg_engine.py           # JdK RRG math, sector constituent resolver, and Plotly rendering engine
├── rrg_watchlists.json     # Isolated custom watchlists storage
├── LAUNCH_RRG_STUDIO.bat   # Windows one-click batch launcher (Port 8502)
└── README.md               # Documentation & workflow
```

---

## ✨ Features Included

1. **Strike.Money 2-Column Split Layout**:
   * **Left Panel**: Watchlist selector, search box, `[✓] Select All` / `[✗] Clear All`, and interactive symbol table with multi-select checkboxes `[x] NAME TAIL PRICE % CHG`.
   * **Right Panel**: Top benchmark sparkline ribbon and pan-enabled, scalable 4-quadrant RRG canvas.
2. **Sector Constituent Drilldown**:
   * Directly queries `sectors.db` to load all constituent stocks for any of the 19 Nifty sector indices.
3. **Movable & Resizable Canvas**:
   * Full panning/dragging (`dragmode="pan"` and `scrollZoom=True`) + canvas height slider (500px to 1000px).
4. **Selectable Benchmarks**:
   * Switch between Nifty 500 (`^CRSLDX`), Nifty 50 (`^NSEI`), Bank Nifty (`^NSEBANK`), or Sector Indices.
5. **Custom Watchlist Manager**:
   * Create, edit, and persist custom watchlists in `rrg_watchlists.json`.
