import { NextResponse } from "next/server";
import { getJob } from "@/lib/mock-data";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const inferenceUrl =
    process.env.INFERENCE_API_URL || "http://localhost:8000";

  try {
    const res = await fetch(
      `${inferenceUrl}/jobs/${encodeURIComponent(id)}`,
      { cache: "no-store" }
    );

    if (!res.ok) {
      throw new Error(`Inference responded ${res.status}`);
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    console.warn(`[jobs/${id}] falling back to mock — inference unavailable:`, e);
    const job = getJob(id);
    if (!job) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }
    return NextResponse.json(job.result);
  }
}
