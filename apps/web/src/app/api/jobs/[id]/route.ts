import { NextResponse } from "next/server";

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

    const bodyText = await res.text();
    let data: unknown;
    try {
      data = JSON.parse(bodyText);
    } catch {
      data = { error: bodyText };
    }

    if (!res.ok) {
      return NextResponse.json(data, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (e) {
    console.error("[proxy /api/jobs] inference unavailable:", e);
    return NextResponse.json(
      { error: "Inference service unavailable", detail: String(e) },
      { status: 502 }
    );
  }
}
