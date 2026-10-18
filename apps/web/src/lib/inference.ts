import { NextResponse } from "next/server";

/** Forward real results and errors. A transport failure never produces a verdict. */
export async function proxyInference(path: string, init: RequestInit = {}, responseKind: "json" | "image" = "json") {
  const configuredUrl = process.env.INFERENCE_API_URL?.trim();
  if (!configuredUrl && process.env.VERCEL === "1") {
    return NextResponse.json(
      { detail: "The inference backend has not been configured." },
      { status: 503 },
    );
  }
  const target = (configuredUrl || "http://localhost:8000").replace(/\/+$/, "");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
    const response = await fetch(`${target}${path}`, { ...init, signal: controller.signal });
    if (responseKind === "image" && response.ok) {
      if (!response.headers.get("content-type")?.startsWith("image/png")) {
        return NextResponse.json({ detail: "The backend returned an invalid capture response." }, { status: 502 });
      }
      return new Response(await response.arrayBuffer(), {
        status: response.status,
        headers: { "Content-Type": "image/png", "Cache-Control": "private, no-store" },
      });
    }
    const body: unknown = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch (error) {
    const timedOut = controller.signal.aborted
      || (error instanceof Error && error.name === "AbortError");
    return NextResponse.json(
      { detail: timedOut ? "The inference request timed out." : "The inference backend is unavailable." },
      { status: timedOut ? 504 : 503 },
    );
  } finally {
    clearTimeout(timeout);
  }
}
