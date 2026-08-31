import { NextRequest, NextResponse } from "next/server";

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
    console.error("[proxy /api/inspect] inference unavailable:", e);
    return NextResponse.json(
      { error: "Inference service unavailable", detail: String(e) },
      { status: 502 }
    );
  }
}
