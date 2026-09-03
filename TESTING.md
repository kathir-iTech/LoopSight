# LoopSight — Manual Testing Checklist

Run this **by hand**, against the **live deployed site** (loopsight.vercel.app),
right before submission. This is the real acceptance pass — automated tests
alone are not enough to sign off.

For each item: do the thing under "What to do", then compare what you actually
see against "What 'pass' looks like". Mark `[ ]` → `[x]` only when the observed
behavior matches. If anything deviates, that item FAILS the build even if the
page renders.

> Note on backend mode: if the live backend (currently the AWS Lambda / real
> inference path) is reachable, every upload should run REAL OpenCV computation
> and two different images MUST yield different verdicts. If the backend is
> unreachable, the site falls back to DEMO fixtures — in that case results are
> varied by a hash of the uploaded bytes (same image → same result, different
> image → usually different), but this is explicitly NOT real computation. The
> checklist below marks which expectation applies per item.

---

## 1. Upload a clear / clean image

- **What to do:** Upload a sharp, well-lit photo of a clean 3D-printed surface
  (no visible defects).
- **What "pass" looks like:** The result page loads within ~30s showing a
  decision. A clean image should reasonably resolve to **PASS** (green). The
  Evidence Trace renders the Perception region(s) with real-looking numeric
  evidence (edge continuity, ref. similarity, layer align. dev.), and Section 4
  shows Final Decision `PASS` with human approval `No`. If it shows REVIEW/FAIL,
  that's not automatically wrong (real CV is data-dependent), but note it and
  confirm it is at least a DIFFERENT outcome than a deliberately defective image.

## 2. Upload a blurry image

- **What to do:** Upload a deliberately blurred / low-contrast / out-of-focus
  photo (or a dark, low-light capture) of the same kind of surface.
- **What "pass" looks like:** The result must be **different** from the clean
  image (different decision, different evidence numbers, and/or an evidence gap
  like "low local contrast" surfaced in the Perception card). A blurry image
  resolving to **REVIEW** (yellow) with `human approval required = Yes` is a
  credible outcome. The point: it must NOT be byte-for-byte identical to the
  clean image's result.

## 3. Upload a non-image file

- **What to do:** Try uploading a `.txt`, `.pdf`, or any non-image file.
- **What "pass" looks like:** Either a clean error is shown to the user (no
  crash, no blank white page), OR the app politely rejects it. It must NOT throw
  an unhandled error, hang forever, or dump a raw stack trace to the UI.

## 4. Upload nothing

- **What to do:** Click **Inspect** with no file selected (and without using the
  demo button).
- **What "pass" looks like:** The Inspect button stays disabled (it is disabled
  when `!selectedFile`), so nothing happens. If somehow triggered, it must fail
  gracefully with a user-facing message — never a crash.

## 5. Refresh mid-inspection

- **What to do:** Upload an image, and *immediately* refresh the page or click
  inspect and then press refresh while "Inspecting..." is shown.
- **What "pass" looks like:** Refresh never crashes the app. You may land back
  on the upload page (acceptable) or on a partially-loaded job page, but the app
  must render cleanly with a way to start a new inspection (the "Back to upload"
  / "New inspection" button). No infinite spinner, no white screen.

## 6. Open on mobile Chrome

- **What to do:** Open loopsight.vercel.app on a phone's Chrome browser
  (Android; or iOS Safari if Chrome unavailable). Do a real upload from the
  device photo library. Also try the in-browser camera capture flow if a camera
  is available.
- **What "pass" looks like:** The layout is usable on a narrow screen (buttons
  visible, cards stack, no horizontal overflow that hides content). Upload and
  camera capture work; the result page is readable on mobile. No JS crash.

## 7. Evidence-trace page with an unknown / stale job_id

- **What to do:** Hand-type a bogus job id into the URL, e.g.
  `https://loopsight.vercel.app/job/doesnotexist` (and also try a real but very
  old id if one exists). Also visit `/job/zzzzzz` directly.
- **What "pass" looks like:** A **clean 404** — the page shows "Job not found"
  (or a similar friendly message) plus a "Back to upload" button. It must NOT
  crash, show a raw `<pre>` error, or hang on a spinner.

## 8. Trial runs summary

- **What to do:** After completing items 1–7, record your overall observation.
- **What "pass" looks like:** You can state confidently: "The live site
  produces varied results for varied inputs and fails gracefully on every bad
  input." If you observed ANY identical-result-when-inputs-differ or any crash,
  the build is NOT ready and must be fixed first.

---

### Sign-off

- [ ] Every item above checked `[x]`
- [ ] No crashes, no hangs, no identical-output-for-different-input cases
- [ ] Backend mode confirmed: real compute **or** explicitly demo-mode fallback
- [ ] Date and initials of the human who ran this pass:

**Date:** ________  **Run by:** ________  **URL tested:** ________
