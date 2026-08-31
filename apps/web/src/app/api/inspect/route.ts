import { NextRequest, NextResponse } from "next/server";
import { MOCK_RESULT, createJob } from "@/lib/mock-data";

export async function POST(request: NextRequest) {
  const inferenceUrl =
    process.env.INFERENCE_API_URL || "http://localhost:8000";

  try {
    const formData = await request.formData();

    // Ensure default profile if the frontend did not send one
    if (!formData.get("inspection_profile")) {
      formData.set("inspection_profile", "fdm_print_surface_v1");
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
    console.warn("[inspect] falling back to mock — inference unavailable:", e);
    // Preserve original mock behavior: ignore uploaded content, return a canned result.
    // This keeps the deployed site demoable even when the backend is unreachable from Vercel.
    const jobId = createJob(MOCK_RESULT);
    return NextResponse.json({ job_id: jobId });
  }
}
