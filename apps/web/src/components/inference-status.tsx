"use client";
import { useCallback, useEffect, useState } from "react";

export function InferenceStatus() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(false);
  const check = useCallback(async () => {
    setChecking(true);
    try {
      const response = await fetch("/api/readiness", { cache: "no-store" });
      const data = await response.json();
      setAvailable(response.ok && data.available === true);
    } catch { setAvailable(false); }
    finally { setChecking(false); }
  }, []);
  useEffect(() => { void check(); }, [check]);
  return (
    <button type="button" onClick={check} disabled={checking} aria-live="polite"
      className="flex items-center gap-2 whitespace-nowrap text-xs text-[#8aa0c0] disabled:opacity-70"
      title="Checks backend version and evidence-storage reads; click to refresh">
      <span className={`h-2 w-2 rounded-full ${available === true ? "bg-green-400" : available === false ? "bg-amber-400" : "bg-slate-400"}`} />
      {checking || available === null ? "Checking image analysis…" : available ? "Image analysis available" : "Analysis unavailable · Retry"}
    </button>
  );
}
