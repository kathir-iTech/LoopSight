import { proxyInference } from "@/lib/inference";

export async function GET() {
  return proxyInference("/version", { cache: "no-store" });
}
