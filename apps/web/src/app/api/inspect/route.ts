import { NextRequest, NextResponse } from "next/server";
import { createJob, fixtureByCase, fixtureForFileBytes } from "@/lib/mock-data";

export async function POST(request: NextRequest) {
  const inferenceUrl = process.env.INFERENCE_API_URL;

  const formData = await request.formData().catch(() => new FormData());
  const sampleId = formData.get("sample_id")?.toString()?.trim();
  const profile = formData.get("inspection_profile")?.toString()?.trim() || "water_turbidity_v1";

  // If deployed on Vercel and no external INFERENCE_API_URL is configured, immediately use calibrated fixtures
  if (!inferenceUrl && process.env.VERCEL === "1") {
    let result = null;
    const caseKey = sampleId || formData.get("demo_case")?.toString()?.trim();
    if (caseKey) {
      result = fixtureByCase(caseKey);
    }
    if (!result) {
      const file = formData.get("image") || formData.get("file");
      const hasPatternStr = formData.get("has_pattern")?.toString()?.trim();
      const hasPatternHint = hasPatternStr !== undefined ? hasPatternStr === "true" : undefined;
      const bytes = file instanceof File
        ? new Uint8Array(await file.arrayBuffer())
        : new Uint8Array([0]);
      result = fixtureForFileBytes(bytes, profile, hasPatternHint);
    }
    const jobId = createJob(result, caseKey);
    return NextResponse.json({ job_id: jobId, result, fallback_mode: "calibrated_fixture" });
  }

  const targetUrl = inferenceUrl || "http://localhost:8000";

  try {
    if (!formData.get("inspection_profile")) {
      formData.set("inspection_profile", profile);
    }

    const demoCase = formData.get("demo_case")?.toString()?.trim();
    if (demoCase) {
      formData.set("demo_case", demoCase);
    } else if (process.env.DEMO_MODE === "golden") {
      formData.set("demo_case", process.env.DEMO_CASE || "uncertain");
    }
    if (!formData.get("demo_case") && process.env.FORCE_AMBIGUOUS === "1") {
      formData.set("demo_case", "uncertain");
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);

    const targetEndpoint = sampleId
      ? `${targetUrl}/inspect/sample/${encodeURIComponent(sampleId)}`
      : `${targetUrl}/inspect`;

    const res = await fetch(targetEndpoint, {
      method: "POST",
      body: sampleId ? undefined : formData,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok) {
      throw new Error(`Inference responded ${res.status}`);
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    // Production fail-closed mode when FAIL_CLOSED_PROD=1 is explicitly enabled
    if (process.env.FAIL_CLOSED_PROD === "1") {
      return NextResponse.json(
        { detail: "Inference backend unreachable and FAIL_CLOSED_PROD=1 is active." },
        { status: 503 }
      );
    }

    console.warn("[inspect] falling back to calibrated v2 fixtures — inference unavailable:", e);
    let result = null;
    const caseKey = sampleId || formData.get("demo_case")?.toString()?.trim();
    if (caseKey) {
      result = fixtureByCase(caseKey);
    }
    if (!result) {
      const file = formData.get("image") || formData.get("file");
      const hasPatternStr = formData.get("has_pattern")?.toString()?.trim();
      const hasPatternHint = hasPatternStr !== undefined ? hasPatternStr === "true" : undefined;
      const bytes = file instanceof File
        ? new Uint8Array(await file.arrayBuffer())
        : new Uint8Array([0]);
      result = fixtureForFileBytes(bytes, profile, hasPatternHint);
    }
    const jobId = createJob(result, caseKey);
    return NextResponse.json({ job_id: jobId, result, fallback_mode: "calibrated_fixture" });
  }
}
