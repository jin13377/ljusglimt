# Juggernaut XL vs Z-Image-Turbo Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce two directly comparable 1280×848 WebP test images for one Ljusglimt article, one with Juggernaut XL v9 and one with Z-Image-Turbo.

**Architecture:** Use the existing local ComfyUI workflows and one shared English subject prompt. Write outputs only to a temporary comparison directory, validate each raw image, then open a self-contained local HTML gallery.

**Tech Stack:** Python, ComfyUI REST API, Pillow, local WebP, HTML.

## Global Constraints

- Do not modify `data/news.json` or production image files.
- Generate exactly one image per model.
- Both outputs must be 1280×848 WebP and use the same article subject.
- Reject text, logos, watermarks, blank/flat output, and off-topic motifs.

---

### Task 1: Select shared article and prompt

**Files:**
- Read: `data/news.json`
- Read: `scripts/image_subjects_en.json`

**Interfaces:**
- Produces: article id, title, and one English realistic-scene prompt used by both models.

- [ ] Select one article with a clear visual motif.
- [ ] Confirm the English prompt contains no Swedish title text.

### Task 2: Start and verify ComfyUI

**Files:**
- Read: `G:/ComfyUI/ComfyUI (1)/ComfyUI/extra_model_paths.yaml`

**Interfaces:**
- Produces: local API endpoint responding HTTP 200 and model availability for both workflows.

- [ ] Start the stable ComfyUI server on loopback only.
- [ ] Query `/system_stats` and `/object_info` to verify required models.

### Task 3: Generate exactly two test images

**Files:**
- Create: `.hermes/image-comparison/juggernaut.webp`
- Create: `.hermes/image-comparison/z-image-turbo.webp`

**Interfaces:**
- Consumes: shared prompt and local ComfyUI API.
- Produces: two 1280×848 WebP files.

- [ ] Submit the Juggernaut XL workflow and save its WebP.
- [ ] Submit the official Z-Image-Turbo workflow and save its WebP.

### Task 4: Verify and present

**Files:**
- Create: `.hermes/image-comparison/index.html`

**Interfaces:**
- Consumes: both WebP files.
- Produces: quality report and side-by-side browser comparison.

- [ ] Verify dimensions, pixel standard deviation, subject relevance, text artifacts, and sharpness.
- [ ] Reject and regenerate only a failing image.
- [ ] Base64-embed both approved images into one HTML gallery and open it locally.
