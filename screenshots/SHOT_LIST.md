# Screenshot shot list

Five images. Four for the portfolio chapter slots, one hero. Each must add
something the others don't — never five crops of the same view.

> **Capture the rebuilt report**, not the original `.pbix`. Build it first
> using [`../docs/POWERBI_BUILD_GUIDE.md`](../docs/POWERBI_BUILD_GUIDE.md).
>
> **Nothing gets blurred.** The blur guidance below applied when the report ran
> on live DMRC figures. The rebuild runs on synthetic data, so every number is
> safe to show — and sharp, readable numbers with an honest attribution line on
> the canvas beat blurred ones every time. Keep the blur notes only if you
> choose to also publish a capture of the original file.

**Universal export settings**

- Power BI Desktop → **View → Page view → Actual size** before capturing. Fit-to-page rescales fonts and makes text soft.
- Set Windows display scaling to 100% for the capture session (Settings → Display → Scale). At 125% Power BI renders blurry text that survives into the PNG.
- Capture with **Win + Shift + S** at full-screen, or better: **File → Export → PDF**, then render the PDF page to PNG at 2400px wide. Vector-sourced text stays sharp; a screen grab does not.
- Target **2400px wide** for every image. The portfolio downscales; upscaling is not recoverable.
- Save as PNG, not JPG. Charts have hard edges and flat colour — JPG artefacts show badly on them.
- Blur, never black-box. Gaussian blur radius ~8–12px at 2400px reads as "professionally redacted"; a black rectangle reads as "hiding something."

**What to blur vs. leave readable**

| Blur | Leave readable |
|---|---|
| Station IDs and names | Chart titles and axis labels |
| Absolute footfall per station | Line names (Yellow, Blue, Red…) |
| Station-to-station matrix cell values | Passenger type labels |
| Any raw transaction detail | The four headline KPIs |

The headline KPIs (66M, ₹2.60bn, ₹39.53, +3.4% vs target) are already published in this README's findings section — they are cleared. Keep them sharp. An entirely blurred dashboard tells a recruiter nothing.

---

## 01 — Hero / full dashboard → `01_dashboard_full.png`

**Slot:** portfolio hero card + README top image.

**Setup**

1. Open `dmrc project.pbix` in Power BI Desktop.
2. Clear every slicer (the Clear Filter button, or Ctrl+click each slicer's selection off). The hero must show the unfiltered network — a filtered hero misleads.
3. Actual size, full report page, nothing selected, no visual in focus mode.
4. Export → PDF → render to PNG at 2400px.
5. Blur station-level detail per the table above.

**Check before shipping:** shrink the image to 400px wide. If the KPI row is still readable, it works as a thumbnail. If not, crop tighter — the hero is judged at card size, not full size.

---

## 02 — Interactivity → `02_interactivity.png`

**Slot:** *Faculties · what it does.* The highest-value image in the set.

Your portfolio copy for this chapter promises interactive exploration. A static screenshot cannot demonstrate that. **Two frames side by side can.**

**Setup**

1. Capture frame A: dashboard with no filters applied.
2. Capture frame B: click **Yellow Line** in the line slicer. Every visual cross-filters — trend line, donut, station bars, the matrix.
3. Compose the two frames stacked or side-by-side in one PNG, ~2400px wide total.
4. Label them: `UNFILTERED` / `FILTERED → YELLOW LINE`. Small mono caption, top-left of each frame.
5. Draw a thin accent-coloured outline around the slicer in frame B so the eye finds the cause of the change.

This one image does more work than the other four combined. It is the difference between "he made charts" and "he built a tool."

---

## 03 — How it's built → `03_model_view.png`

**Slot:** *Substratum · how it's built.*

Use **`docs/pipeline.svg`** (already in this repo) as the primary image. It is the only slot where a diagram beats a screenshot — recruiters skim here to judge technical depth, and a chart cannot show a pipeline.

**Optional stronger version:** compose the pipeline diagram on top with a strip beneath it showing either

- Power BI's **Model view** (the relationship diagram), or
- a code fragment of the rolling-average window function from `sql/02_analysis_queries.sql`, syntax-highlighted on the same dark background.

Keep it dark (#0a0a0c background) so it sits flush with your portfolio's chapter panels.

---

## 04 — Impact → `04_kpi_detail.png`

**Slot:** *Culmination · the impact.*

Impact means numbers, and numbers must be legible.

**Setup**

1. Crop tightly to the **KPI card row** plus the **daily-average-vs-target** visual.
2. Leave those figures completely sharp. This is the one image with no blur.
3. Optionally add the donut showing 51.16% line concentration beside them — it is your single most interesting finding and it reads clearly even small.
4. ~2400px wide, letterboxed rather than tall.

---

## 05 — The brief → `reference_spec.png`

**Slot:** *Genesis · the origin.*

This is the prototype your DMRC mentor supplied as the target specification — the existing `dashboard_preview.png`. Rename it to `reference_spec.png`.

**Non-negotiable:** it must be captioned as the mentor's reference, not your build. Presenting someone else's design as your own is the one thing that can sink the whole project in an interview.

**Two ways to use it**

- **Simple:** the prototype alone, captioned *"The reference specification we were handed."*
- **Better:** a two-panel `SPEC → BUILT` comparison — mentor prototype left, your dashboard right. This turns the awkward fact into the strongest possible origin story: *here is what we were asked for, here is what we shipped.* Recruiters read that as delivery against a requirement, which is exactly what the job is.

---

## Order of work

1. Take frame A (unfiltered full page) — feeds both **01** and **02**.
2. Take frame B (Yellow Line selected) — feeds **02**.
3. Crop **04** out of frame A. No re-capture needed.
4. **03** is already done (`docs/pipeline.svg`).
5. Rename and caption **05**.

Two captures, three crops, one rename. Under an hour.
