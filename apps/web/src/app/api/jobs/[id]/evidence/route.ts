import { proxyInference } from "@/lib/inference";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyInference(`/jobs/${encodeURIComponent(id)}/evidence`, { cache: "no-store" }, "archive");
}
