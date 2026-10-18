import { NextResponse } from "next/server";
import { getJob } from "@/lib/mock-data";
import { proxyInference } from "@/lib/inference";
import { MEASUREMENT_CONTRACT } from "@/lib/measurements";

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
      measurement_contract: MEASUREMENT_CONTRACT,
      provenance: { execution_mode: "demo_fixture" },
    });
  }
  return proxyInference(`/jobs/${encodeURIComponent(id)}`, { cache: "no-store" });
}
