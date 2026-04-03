Here’s a crisp, **light spec** for the **POI (a.k.a. “PIO”) feature** your dev team can ship. No code—just clear contracts, flows, and acceptance criteria.

# POI Feature Spec (v0.1)

## 1) Purpose & Outcomes

Enable researchers to:

* Define **Points of Interest (POIs)** tied to **research goals**.
* Address evidence **precisely** within audio files by **time ranges** (canonical) and **optional chunk ranges** (fast deep-linking).
* Jump directly to a POI in the web app, **seek playback**, and **highlight spans** on the spectrogram with relevant indices.

**Success =** a researcher can create, find, and revisit POIs reliably across projects with different file durations and chunk scales—**no magic numbers** in code.

---

## 2) Glossary (project-wide)

* **Project**: A dataset/config set (drives display width/height and nominal file duration).
* **Config Name**: The YAML used for processing (e.g., `config_multi_species_frogs.yaml`).
* **Processing Type**: `temporal`, `spectral`, or `poi` (defines the chunk grid).
* **Scale**: A tuple of `(config_name, processing_type) → chunk_duration_sec`.
* **Span**: A continuous region of interest in a file (seconds-first; chunk indices optional).

---

## 3) Scope

**In-scope**

* Create/list/update/delete **Goals**, **POIs**, and **Spans**.
* Store **seconds** as canonical POI addressing.
* Optionally store **chunk indices** + the **scale** they refer to (for deep-link & snapping).
* Deep link route `/#/poi/:pid` that opens viewer, seeks to the first span, and paints overlays.
* Read chunk scale from **YAML** (not hard-coded).

**Out-of-scope (v0.1)**

* Cross-file editing of a single span (POI can still have multiple spans across files).
* Model training integration.
* User roles/ACL beyond basic author tracking (see §10 for future).

---

## 4) Data Model Changes (descriptions only)

> Keep seconds canonical; chunks are optional sugar with an explicit scale.

**A. Projects**

* Store UI defaults (PNG width/height, nominal file duration) and link files to a project.

**B. Processing Scales Registry**

* Table/registry mapping `(config_name, processing_type)` → `chunk_duration_sec`.
* Populated at process time by reading YAML. One row per unique scale.

**C. Stamps on Data**

* `audio_files.config_name` (which YAML processed it).
* `acoustic_indices_core.config_name` (same).
* Indices already have start times; chunk/window sec can be resolved via the scale registry.

**D. Research Goals**

* `id, title, description, created_at`.

**E. Points of Interest**

* `id, goal_id, project_id (optional)`, `label`, `notes`, `confidence (0..1)`, `anchor_index_name (optional)`, `created_at`.

**F. POI Spans**

* `poi_id, file_id`, **canonical**: `start_time_sec, end_time_sec`.
* **optional** chunk addressing: `chunk_start, chunk_end (inclusive)`, plus `config_name` and `processing_type` to bind those chunks to a scale.

**G. Optional Evidence Snapshot (nice-to-have)**

* Lightweight copy of index values at POI creation for auditability (keyed by `poi_id`).

---

## 5) Config Integration (no code)

* At ingest/process time, parse YAML for:

  * `file_duration_sec` (if present),
  * `acoustic_indices.temporal.chunk_duration_sec` (if any),
  * `acoustic_indices.spectral.chunk_duration_sec` (if any),
  * optional `poi.chunk_duration_sec` if you add it.
* Upsert to the **Processing Scales** registry.
* Stamp `config_name` on `audio_files` and `acoustic_indices_core`.

**Display scale**: compute `seconds_per_px = file_duration_sec / png_width_px` using the YAML/UI defaults for the active project.

---

## 6) API Surfaces (no code; shapes & examples)

### Goals

* `POST /api/goals` → `{title, description?}` → `{id, ...}`
* `GET /api/goals` / `GET /api/goals/:id`

### POIs

* `POST /api/poi`
  **Body example**

  ```json
  {
    "goal_id": 12,
    "project_id": 1,
    "label": "GG Bell frog candidate",
    "notes": "Clean call; minimal wind",
    "confidence": 0.8,
    "anchor_index_name": "bai_l_aurea",
    "spans": [
      {
        "file_id": 3456,
        "start_time_sec": 504.0,
        "end_time_sec": 526.5,
        "chunk_start": 112,
        "chunk_end": 117,
        "config_name": "config_multi_species_frogs.yaml",
        "processing_type": "spectral"
      }
    ]
  }
  ```
* `GET /api/poi/:pid` → returns POI, spans (with resolved **file metadata**, **seconds**, **optional chunk**), and **scale info** (lookup or inline).
* `GET /api/poi?goal_id=…` / `?file_id=…` / `?date=…`
* `PATCH /api/poi/:pid` → update label/notes/confidence; add/remove spans.
* `DELETE /api/poi/:pid`

**Indices for a span (viewer convenience)**

* `GET /api/indices/:file_id?start=<sec>&end=<sec>` → return only rows intersecting the span (viewer overlays).

---

## 7) Deep Link Contract

* Route: `/#/poi/:pid`
* Optional query for multi-span open behavior: `?span=i` (default `i=0`).
* Viewer responsibilities on load:

  1. Fetch POI and spans.
  2. For the selected span:

     * Seek audio to `start_time_sec`.
     * Compute `x_px` from `seconds_per_px`.
     * Paint overlay rectangles for all spans of this POI on the spectrogram.
  3. Sidebar: show label, notes, confidence, anchor index; mini-table of indices for current span.

---

## 8) UI/UX Flows

**A. Create POI (from viewer)**

1. User drags to select a time window on the spectrogram (snap-to-chunk toggle on/off).
2. “Add POI” dialog:

   * Goal (required; select or create),
   * Label (short),
   * Notes (freeform),
   * Confidence (slider 0..1),
   * Anchor Index (dropdown from available index streams).
3. Save → posts POI with a single span.
4. Toast: “Saved. View POI” → pushes `/#/poi/:pid`.

**B. Add additional spans**

* From the same POI, user can add another selection (same file or different file).

**C. List & Filter**

* Goals view → list POIs grouped by goal, with quick filters (date range, config, file).

**D. Visuals**

* Spans rendered as translucent bands; on hover show start/end (sec), chunk range (if present), and scale `(config_name, processing_type)`.

**E. Snapping**

* If snapping enabled, snap edges to chunk boundaries using the active scale for the file/config; show chunk labels in the hover.

---

## 9) Migration & Backfill (sequence)

1. Add `projects`, `processing_scales`, POI tables; add `config_name` to `audio_files` and `acoustic_indices_core`.
2. During next processing run, stamp `config_name` and upsert scales from YAML.
3. (Optional) Backfill older rows by inferring config\_name where known (e.g., by path or run log); if unknown, POIs will still work by **seconds**.

---

## 10) Observability, Audit, & Permissions

* **Audit**: Track `created_by`, `updated_by` on POIs and spans (user id or email).
* **Telemetry**: Log POI creation, edits, deletes, and viewer deep-link opens (for usage analytics).
* **Permissions (v0.1)**: Anyone in the project can view POIs; only creator or admins can edit/delete (simple rule).
* **(Optional)** Evidence snapshot table to pin index values at creation time.

---

## 11) Performance & Indexing

* DB indexes:

  * `poi_spans(file_id, start_time_sec, end_time_sec)`
  * `acoustic_indices_core(file_id, start_time_sec)`
  * `points_of_interest(goal_id)`
* Cache project display defaults per project in memory (seconds\_per\_px, png dims).
* Paginate POI lists; lazy-load indices for spans on demand.

---

## 12) Edge Cases & Rules

* **Different chunk scales** across indices: render by time; show chunk ranges only when `(config_name, processing_type)` is present.
* **Missing scale row**: if `(config_name, processing_type)` not found, hide chunk UI and continue with seconds.
* **Very short files**: POIs must be within `[0, duration_seconds]`.
* **Overlapping spans**: allowed; viewer should stack overlays with slight offset or outline.
* **Reprocessing** with new config: historic POIs remain valid via seconds; chunk labels may differ (that’s expected).

---

## 13) Acceptance Criteria (v0.1)

1. **Create POI** from a selection and deep-link to it via `/#/poi/:pid`.
2. **Render overlays** for all spans of a POI; seek playback to active span start.
3. **Show indices** table filtered to the current span’s time window.
4. **Seconds canonical**: All POIs remain valid even if project chunk size changes.
5. **Chunk optional**: When scale is known, show chunk ranges; when not, feature still works via seconds.
6. **Config-driven**: No hard-coded 900s or 4.5s in the viewer or API; values come from YAML/DB.

---

## 14) Example Objects (illustrative, not code)

**POI (GET)**

```json
{
  "id": 101,
  "goal_id": 12,
  "project_id": 1,
  "label": "GG Bell frog candidate",
  "notes": "Series of clean pulses; minimal wind",
  "confidence": 0.8,
  "anchor_index_name": "bai_l_aurea",
  "created_at": "2025-08-19T06:55:00Z",
  "spans": [
    {
      "file_id": 3456,
      "start_time_sec": 504.0,
      "end_time_sec": 526.5,
      "chunk_start": 112,
      "chunk_end": 117,
      "config_name": "config_multi_species_frogs.yaml",
      "processing_type": "spectral"
    }
  ],
  "links": {
    "deep_link": "/#/poi/101"
  }
}
```

**Scale Registry (concept)**

```json
[
  {"config_name": "config_multi_species_frogs.yaml", "processing_type": "spectral", "chunk_duration_sec": 4.5},
  {"config_name": "config_multi_species_frogs.yaml", "processing_type": "temporal", "chunk_duration_sec": 4.5},
  {"config_name": "config_mac.yaml", "processing_type": "spectral", "chunk_duration_sec": 3.0}
]
```

---

## 15) Open Questions (to confirm before build)

1. Do we want a **dedicated `poi` scale** in YAML (e.g., `poi.chunk_duration_sec`) or always reuse `temporal/spectral`?
2. Should cross-file **multi-span creation** be enabled in v0.1, or added in v0.2?
3. Do we need **tagging** on POIs (e.g., `species: ["L. aurea"]`) in v0.1?
4. Keep **evidence snapshots** in v0.1, or defer?

---

### TL;DR

* **Seconds-first POIs** with optional **chunk** addressing bound to `(config_name, processing_type)` from YAML.
* **Deep link** `/#/poi/:pid`, seek + overlay + indices in viewer.
* **No magic numbers**—display and chunk scales are **config-driven**.

