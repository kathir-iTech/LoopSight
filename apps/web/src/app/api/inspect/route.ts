import { NextRequest, NextResponse } from "next/server";
import { createJob, fixtureByCase, fixtureForFileBytes } from "@/lib/mock-data";

export async function POST(request: NextRequest) {
  const inferenceUrl =
    process.env.INFERENCE_API_URL || "http://localhost:8000";

  const formData = await request.formData().catch(() => new FormData());

  try {
    // Ensure default profile if the frontend did not send one
    if (!formData.get("inspection_profile")) {
      formData.set("inspection_profile", "fdm_print_surface_v1");
    }

    // Demo resilience: when the backend is in DEMO_MODE=golden, or the web
    // app is configured to force the ambiguous case, pass the golden case
    // selector through so the demo never depends on a live API call.
    const demoCase = formData.get("demo_case")?.toString()?.trim();
    if (demoCase) {
      formData.set("demo_case", demoCase);
    } else if (process.env.DEMO_MODE === "golden") {
      // Respect a web-app-level default, if set
      formData.set("demo_case", process.env.DEMO_CASE || "uncertain");
    }
    // FORCE_AMBIGUOUS=1 guarantees the uncertain branch fires on command
    if (!formData.get("demo_case") && process.env.FORCE_AMBIGUOUS === "1") {
      formData.set("demo_case", "uncertain");
    }

    const res = await fetch(`${inferenceUrl}/inspect`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error(`Inference responded ${res.status}`);
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    console.warn("[inspect] falling back to DEMO fixtures — inference unavailable:", e);
    // DEMO MODE fallback (not real computation — see lib/mock-data.ts comment).
    // Previously this returned the SAME canned result for every upload, so two
    // different images looked identical. Now we pick a fixture deterministically
    // from the uploaded bytes (or an explicit demo_case): same image -> same
    // result, different images -> usually different results. Still demo data,
    // never the real OpenCV pipeline — that requires the live backend.
    let result = null;
    const demoCase = formData.get("demo_case")?.toString()?.trim();
    if (demoCase) {
      result = fixtureByCase(demoCase);
    }
    if (!result) {
      const file = formData.get("image") || formData.get("file");
      const bytes = file instanceof File
        ? new Uint8Array(await file.arrayBuffer())
        : new Uint8Array([0]);
      result = fixtureForFileBytes(bytes);
    }
    const jobId = createJob(result);
    return NextResponse.json({ job_id: jobId });
  }
}
