import { NextResponse } from "next/server";
import { getJob } from "@/lib/mock-data";
import { proxyInference } from "@/lib/inference";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (process.env.DEMO_MODE === "golden") {
    const job = getJob(id);
    if (!job) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }
    return NextResponse.json({
      ...job.result,
      provenance: { execution_mode: "demo_fixture" },
    });
  }
  return proxyInference(`/jobs/${encodeURIComponent(id)}`, { cache: "no-store" });
}
