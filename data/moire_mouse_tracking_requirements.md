# Moiré Mouse Tracking Project Requirements

## 1) Project overview

**Goal:** Build a desktop app that renders controlled moiré gratings in
an overlay, estimates the pointer's position from the moiré phase, and
compares it---live---to the OS mouse coordinates. Show a visual of the
moiré sampling area and report accuracy stats.

**Success criteria (quantitative):** - Relative precision (after
smoothing): ≤ **0.05 px RMS** per axis (stretch: 0.02 px). - Absolute
accuracy across screen (after one-time calibration/LUT): ≤ **0.3 px mean
abs. error**, ≤ **0.6 px** 95th percentile.

## 2) Scope

-   Platforms: Windows 10+ (primary). Nice-to-have: macOS 13+.
-   Inputs: none (mouse and screen are the "sensors").
-   Outputs: overlay UI, numeric metrics, CSV log.

## 3) Definitions

-   **Reference layer**: fixed sinusoidal gratings (x & y) anchored to
    desktop coordinates.
-   **Probe layer**: small draggable/trackable patch aligned to mouse;
    used to read phase.
-   **Beat/moire phase**: envelope phase from two close spatial
    frequencies per axis.
-   **LUT**: per-monitor lookup table mapping measured phase → absolute
    pixels.

## 4) Functional requirements

### 4.1 Overlay & visualization

-   Renders a **borderless, click-through, always-on-top** overlay
    spanning the display(s).
-   Shows:
    -   **Grating region(s)** (rectangles) with adjustable size (default
        **256×256 px**), position (follows mouse or fixed).
    -   **Reference crosshair** at overlay center.
    -   **Mouse marker** (from OS): small dot with label `OS: (x,y)`.
    -   **Moiré-estimated marker**: small square with label
        `Moire: (x̂,ŷ)`.
    -   **Error vector** arrow from moiré marker to OS marker; legend
        with `Δx, Δy, |Δ|`.
    -   A translucent **"sampling ROI"** mask that shows exactly which
        pixels contribute to the phase readout.
-   Toggle panel (hotkey **F8**) for parameters; hotkey **F9**
    start/stop logging; **F10** start/stop calibration.

### 4.2 Mouse ground truth

-   Read OS cursor position each frame (Windows: `GetCursorPos`).
-   Optionally snap to pixel centers for reproducible testing.

### 4.3 Grating patterns

-   X-axis grating: (g_x(x)=0.5+0.5`\cos`{=tex}(2`\pi `{=tex}f_x
    x+`\phi`{=tex}\_{x0}))
-   Y-axis grating: (g_y(y)=0.5+0.5`\cos`{=tex}(2`\pi `{=tex}f_y
    y+`\phi`{=tex}\_{y0}))
-   Two nearby frequencies per axis for unwrapping:
    -   Default: (f_x\^{(1)}=0.200) cyc/px, (f_x\^{(2)}=0.200+1/256)
    -   Same for y. Contrast 30%, Hann window inside ROI to reduce
        leakage.
-   Rendering in linearized sRGB or keep contrast ≤40% to reduce gamma
    bias.

### 4.4 Phase measurement

-   Per frame:
    1)  Capture ROI bitmap(s) directly from the overlay layer (no
        camera).
    2)  For each axis & frequency, compute I/Q by correlation with
        sin/cos templates (or 1D FFT per row, average).
    3)  Phase (`\phi`{=tex}=`\mathrm{atan2}`{=tex}(Q,I)); beat/envelope
        phase
        (`\Phi`{=tex}=`\mathrm{unwrap}`{=tex}(`\phi`{=tex}\_2-`\phi`{=tex}\_1)).
    4)  Convert (`\Phi`{=tex}) → displacement using calibrated LUT (no
        linear model required).
-   Temporal smoothing: exponential moving average with configurable
    half-life (default 100 ms).

### 4.5 Calibration (one-time per monitor & scale)

-   Wizard moves the probe region over a grid (default 16×9 points
    across the current monitor).
-   At each grid node, dwell 150 ms, collect 30 frames → average phases
    ((`\Phi`{=tex}\_x\^{(1)},`\Phi`{=tex}\_x\^{(2)},`\Phi`{=tex}\_y\^{(1)},`\Phi`{=tex}\_y\^{(2)})).
-   Build **per-axis LUTs**:
    -   Option A (direct): map combined phase vector → (x,y) by
        nearest-neighbor in phase space + bilinear interpolation across
        grid.
    -   Option B (CRT-style): fuse two frequencies to unwrap to a wide
        effective period, then spline-fit (`\Phi `{=tex}`\to `{=tex})
        pixels.
-   Persist calibration as JSON tied to **monitor EDID**, resolution,
    and DPI scaling.

### 4.6 Metrics & logging

-   Live HUD:
    -   `OS: (x,y)`, `Moire: (x̂,ŷ)`, `Δx`, `Δy`, `|Δ|`, `FPS`,
        `σ_phase`.
-   CSV log (10--60 Hz): timestamp, monitor id, params, OS coords, moiré
    coords, error, ROI size, smoothing factor.
-   "Hold-still" test mode: compute RMS error over the last N frames;
    "Sweep" mode: script a mouse path and report per-segment error.

### 4.7 Configuration

-   JSON file with:
    -   Frequencies per axis, ROI size, contrast, smoothing, capture
        backend, hotkeys.
    -   Calibration blobs per monitor/DPI.
-   UI panel to tweak and save/load profiles.

## 5) Non-functional requirements

-   **Latency:** end-to-end \< **25 ms** (goal), \< 50 ms (max).
-   **Throughput:** 60 FPS target; degrade gracefully to 30 FPS.
-   **CPU/GPU:** ≤ 20% of one modern CPU core for phase math; optional
    GPU offload is a plus.
-   **Stability:** overlay never steals clicks; robust on multi-monitor.
-   **Privacy:** no screen content leaves machine; logs stored locally.

## 6) Architecture

-   **Overlay renderer** (C++/C# w/ Direct2D/DirectComposition or DXGI;
    on macOS, CoreGraphics/Metal).
-   **Capture** of overlay region (copy from backbuffer or OS
    compositor) to avoid background app noise.
-   **Phase engine** (C++/Rust or Python+Numba for prototype): ROI
    windowing, I/Q correlation, unwrap, smoothing.
-   **Calibration manager**: grid runner, phase collection, LUT builder,
    JSON store.
-   **UI module**: parameter panel, HUD, hotkeys.
-   **Logger**: CSV writer, rolling files.

## 7) Parameter defaults (good starting point)

-   ROI: **256×256 px** square centered on cursor.
-   Frequencies: (f\^{(1)}=0.200), (f\^{(2)}=0.200+1/256) cyc/px (both
    axes).
-   Contrast: 0.3; Hann window 10% taper.
-   Smoothing: EMA with α such that half-life = 6 frames (\~100 ms @ 60
    FPS).
-   Calibration grid: 16×9; dwell 150 ms; 30 frames averaged.

## 8) Evaluation protocol (acceptance tests)

1)  **Static hold**: Place mouse at 20 random points (scripted). Record
    2 s each.
    -   Pass if RMS error per point ≤ **0.2 px** median, ≤ **0.4 px**
        95th percentile.
2)  **Slow sweep**: Script linear paths across each axis (1000 px in 2
    s).
    -   Pass if mean abs. error ≤ **0.3 px**, max ≤ **0.8 px**.
3)  **Full-screen zigzag**: Cover \~70% of screen area in 10 s.
    -   Pass if global mean abs. error ≤ **0.3 px**.
4)  **Stress**: Change Windows scaling (100%→125%→150%), re-run
    calibration; metrics remain within pass bands.
5)  **Noise sensitivity**: Reduce contrast to 15% → error increases
    gracefully (\<2×).

## 9) Risks & mitigations

-   **DPI/gamma nonlinearity** → Use calibration LUT + moderate
    contrast; per-monitor profiles.
-   **Subpixel RGB layout differences** → Stick to cos gratings, not
    ultra-thin lines; keep freq \< 0.25 cyc/px.
-   **Compositor artifacts** → Capture from overlay backbuffer; avoid
    relying on background content.
-   **Multi-display drift** → Anchor gratings to per-monitor
    coordinates; separate LUTs.

## 10) Deliverables

-   Executable app (Windows) with overlay, calibration wizard, live HUD,
    CSV logs.
-   `config.json` and `calibration.json`.
-   Short user guide (README) describing hotkeys and test protocol.
-   (Optional) Python notebook to analyze logs and plot error
    histograms.

## 11) Stretch features

-   Dual-ROI fusion for better SNR (two patches near cursor).
-   3-frequency unwrapping for ultra-wide unambiguous range.
-   Auto-recalibration when EDID/DPI changes.
-   macOS build (AX-aware variant) and Linux build.
