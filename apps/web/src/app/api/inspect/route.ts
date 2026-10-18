import { NextRequest, NextResponse } from "next/server";
import { createJob, fixtureByCase } from "@/lib/mock-data";
import { proxyInference } from "@/lib/inference";
import { MEASUREMENT_CONTRACT } from "@/lib/measurements";

export async function POST(request: NextRequest) {
  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ detail: "Expected multipart form data." }, { status: 400 });
  }
  const sampleId = formData.get("sample_id")?.toString()?.trim();

  // Fixtures require an explicitly selected demonstration mode.
  if (process.env.DEMO_MODE === "golden") {
    const caseKey = sampleId || formData.get("demo_case")?.toString()?.trim()
      || process.env.DEMO_CASE || "uncertain";
    const fixture = fixtureByCase(caseKey);
    if (!fixture) {
      return NextResponse.json({ detail: "Unknown demonstration case." }, { status: 404 });
    }
    const result = {
      ...fixture,
      measurement_contract: MEASUREMENT_CONTRACT,
      provenance: { execution_mode: "demo_fixture" as const },
    };
    const jobId = createJob(result, caseKey);
    return NextResponse.json({ job_id: jobId, result });
  }

  // Request fields cannot silently switch real inspection into a fixture.
  formData.delete("demo_case");
  if (!formData.get("inspection_profile")) {
    formData.set("inspection_profile", "water_turbidity_v1");
  }
  return proxyInference(
    sampleId ? `/inspect/sample/${encodeURIComponent(sampleId)}` : "/inspect",
    { method: "POST", body: sampleId ? undefined : formData },
  );
}
