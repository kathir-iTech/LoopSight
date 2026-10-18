import { NextResponse } from "next/server";
import { proxyInference } from "@/lib/inference";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; index: string }> },
) {
  const { id, index } = await params;
  if (index !== "0" && index !== "1") {
    return NextResponse.json({ detail: "Capture not found" }, { status: 404 });
  }
  return proxyInference(`/jobs/${encodeURIComponent(id)}/captures/${index}`, { cache: "no-store" }, "image");
}
