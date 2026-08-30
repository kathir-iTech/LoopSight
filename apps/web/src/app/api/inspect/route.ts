import { NextRequest, NextResponse } from "next/server";
import { MOCK_RESULT, createJob } from "@/lib/mock-data";

export async function POST(request: NextRequest) {
  await request.formData();
  const jobId = createJob(MOCK_RESULT);
  return NextResponse.json({ job_id: jobId });
}
