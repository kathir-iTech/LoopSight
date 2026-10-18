import { NextResponse } from "next/server";
import { proxyInference } from "@/lib/inference";

export async function GET() {
  const [version, ready] = await Promise.all([
    proxyInference("/version", { cache: "no-store" }),
    proxyInference("/ready", { cache: "no-store" }),
  ]);
  if (!version.ok || !ready.ok) {
    return NextResponse.json({ available: false, detail: "Image analysis is unavailable. Please retry shortly." },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  const data = await version.json();
  return NextResponse.json({ available: true, opencv_version: data.opencv_version,
    build_revision: data.build_revision, runtime_architecture: data.runtime_architecture,
    shared_storage: data.storage?.shared_across_instances === true,
    physical_units_available: data.measurement_contract?.physical_units_available === true,
    storage_write_verified: false }, { headers: { "Cache-Control": "no-store" } });
}
