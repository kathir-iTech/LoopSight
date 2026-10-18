import { NextResponse } from "next/server";
import { getJob } from "@/lib/mock-data";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const inferenceUrl = process.env.INFERENCE_API_URL;

  // On Vercel without external inference server, resolve directly from resilient store
  if (!inferenceUrl && process.env.VERCEL === "1") {
    const job = getJob(id);
    if (!job) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }
    return NextResponse.json(job.result);
  }

  const targetUrl = inferenceUrl || "http://localhost:8000";

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const res = await fetch(
      `${targetUrl}/jobs/${encodeURIComponent(id)}`,
      { cache: "no-store", signal: controller.signal }
    );
    clearTimeout(timeout);

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
