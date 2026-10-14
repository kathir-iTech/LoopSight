"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { InspectionResult } from "@/lib/types";
import { saveToHistory, loadHistory } from "@/lib/history";
import toast from "react-hot-toast";
import {
  ArrowDown,
  AlertTriangle,
  XCircle,
  Copy,
  Download,
  Share2,
  RefreshCw,
  Droplets,
  Eye,
  Sun,
  Waves,
  ShieldAlert,
  Camera,
  Upload,
  X,
  Ruler,
  Cpu,
} from "lucide-react";
import jsPDF from "jspdf";

function hasReference(result: InspectionResult): boolean {
  const gapMentionsRef = result.evidence_gap.some((g) => g.toLowerCase().includes("reference"));
  const anyNonOne = result.regions.some((r) => Math.abs(r.evidence.reference_similarity - 1.0) > 0.001);
  const secondHasRef =
    result.second_pass?.regions.some(
      (r) =>
        r.reference_similarity !== undefined &&
        typeof r.reference_similarity === "number" &&
        Math.abs((r.reference_similarity as number) - 1.0) > 0.001
    ) ?? false;
  return gapMentionsRef || anyNonOne || secondHasRef;
}

function isWaterResult(result: InspectionResult): boolean {
  if (result.inspection_profile === "water_turbidity_v1") return true;
  if (result.inspection_profile && result.inspection_profile !== "water_turbidity_v1") return false;
  if (
    result.evidence_gap.some(
      (g) =>
        g.toLowerCase().includes("pattern visibility") ||
        g.toLowerCase().includes("pattern not detected") ||
        g.toLowerCase().includes("through water") ||
        g.toLowerCase().includes("stratification") ||
        g.toLowerCase().includes("specular glass glare")
    )
  )
    return true;
  if (result.regions.some((r) => r.evidence.pattern_visibility !== undefined && r.evidence.pattern_visibility > 0))
    return true;
  return false;
}

function isCrackResult(result: InspectionResult): boolean {
  if (result.inspection_profile === "structural_crack_metrology_v1") return true;
  if (result.regions.some((r) => (r.evidence.crack_width_mm ?? 0) > 0 || (r.evidence.crack_severity_score ?? 0) > 0))
    return true;
  return false;
}

function ClarityGauge({ value, label, sublabel }: { value: number; label: string; sublabel?: string }) {
  const pct = Math.max(0, Math.min(1, value));
  const statusColor = pct <= 0.20 ? "#ef4444" : pct >= 0.55 ? "#38bdf8" : "#f59e0b";
  const statusText = pct <= 0.20 ? "Turbid" : pct >= 0.55 ? "Clear" : "Borderline";
  const circumference = 2 * Math.PI * 38;
  const offset = circumference * (1 - pct);
  const gradId = `grad-${label.replace(/\s+/g, "")}-${Math.round(pct * 100)}`;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-[104px] h-[104px] flex items-center justify-center">
        <svg width={104} height={104} viewBox="0 0 104 104" className="rotate-[-90deg]">
          <circle cx={52} cy={52} r={38} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={8} />
          <defs>
            <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="40%" stopColor="#f59e0b" />
              <stop offset="75%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#0ea5e9" />
            </linearGradient>
          </defs>
          <circle
            cx={52}
            cy={52}
            r={38}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 900ms ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[17px] font-bold tracking-tight" style={{ color: statusColor }}>
            {(pct * 100).toFixed(0)}%
          </span>
          <span className="text-[10px] tracking-widest uppercase" style={{ color: statusColor }}>
            {statusText}
          </span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-xs font-medium text-white">{label}</p>
        {sublabel && <p className="text-[11px] text-[#8aa0c0]">{sublabel}</p>}
        <p className="text-[11px] font-mono text-[#8aa0c0] mt-0.5">{value.toFixed(3)}</p>
      </div>
    </div>
  );
}

function ClarityBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-[11px]">
        <span className="text-[#ef4444]">Turbid (≤0.20)</span>
        <span className="text-[#f59e0b]">Borderline</span>
        <span className="text-[#38bdf8]">Clear (≥0.55)</span>
      </div>
      <div
        className="relative h-3 rounded-full overflow-hidden border border-white/10"
        style={{ background: "rgba(255,255,255,0.06)" }}
      >
        <div
          className="absolute inset-0 rounded-full"
          style={{ background: "linear-gradient(90deg, #ef4444 0%, #f59e0b 38%, #38bdf8 72%, #0ea5e9 100%)", opacity: 0.95 }}
        />
        <div className="absolute top-0 bottom-0 w-px bg-white/80" style={{ left: "20%" }} />
        <div className="absolute top-0 bottom-0 w-px bg-white/80" style={{ left: "55%" }} />
        <motion.div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-[#0a1628] shadow-lg"
          initial={{ left: "0%" }}
          animate={{ left: `calc(${pct}% - 6px)` }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </div>
      <div className="flex justify-between text-[11px] font-mono text-[#8aa0c0]">
        <span>0.20</span>
        <span>0.55</span>
      </div>
    </div>
  );
}

function DecisionCard({ result }: { result: InspectionResult }) {
  const { decision, confidence_band, human_approval_required, reasoning } = result.final_decision;
  const water = isWaterResult(result);
  const crack = isCrackResult(result);
  const styles: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode; safety: string }> = {
    PASS: {
      bg: "bg-[#38bdf8]/10",
      border: "border-[#38bdf8]/30",
      text: "text-[#38bdf8]",
      icon: <Waves className="h-6 w-6 text-[#38bdf8]" />,
      safety: water
        ? "No visible turbidity detected — this does not confirm the water is safe. Invisible contaminants (arsenic, fluoride, nitrate) require a real water test."
        : crack
        ? "No structural fracture detected (<0.15mm threshold) — surface shadow or reflection artifact cleared by second-pass metrology."
        : "No defect signal — confident pass.",
    },
    REVIEW: {
      bg: "bg-[#f59e0b]/10",
      border: "border-[#f59e0b]/30",
      text: "text-[#f59e0b]",
      icon: <AlertTriangle className="h-6 w-6 text-[#f59e0b]" />,
      safety: water
        ? "Visible turbidity detected — this water should not be consumed without treatment or further testing. Borderline case — try a photo under different lighting or get a lab test."
        : "Uncertain — human review required.",
    },
    FAIL: {
      bg: "bg-[#ef4444]/10",
      border: "border-[#ef4444]/30",
      text: "text-[#ef4444]",
      icon: <XCircle className="h-6 w-6 text-[#ef4444]" />,
      safety: water
        ? "Visible turbidity detected — this water should not be consumed without treatment or further testing. Pattern strongly obscured through the sample."
        : crack
        ? "Structural fracture detected (width ≥ 0.40mm threshold) — requires civil/structural engineering inspection."
        : "Defect confidently detected.",
    },
    NO_PATTERN_DETECTED: {
      bg: "bg-[#64748b]/10",
      border: "border-[#64748b]/30",
      text: "text-[#94a3b8]",
      icon: <Eye className="h-6 w-6 text-[#94a3b8]" />,
      safety:
        "No checkerboard pattern detected — ensure the printed grid is visible behind the water sample and retake the photo. No turbidity verdict can be given on this image.",
    },
  };
  const s = styles[decision] || styles.REVIEW;
  return (
    <Card className={`${s.bg} ${s.border} border-2 overflow-hidden`}>
      <CardContent className="p-6">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${s.bg} border ${s.border}`}>
            {s.icon}
          </div>
          <div className="flex-1">
            <p className="text-xs uppercase tracking-widest text-[#8aa0c0]">Final Deterministic Decision</p>
            <p className={`text-2xl font-bold tracking-tight ${s.text}`}>{decision}</p>
          </div>
          <Badge
            variant={
              decision === "PASS"
                ? "success"
                : decision === "FAIL"
                ? "destructive"
                : decision === "NO_PATTERN_DETECTED"
                ? "outline"
                : "warning"
            }
            className="text-sm px-3 py-1"
          >
            {decision === "NO_PATTERN_DETECTED" ? "no pattern" : `${confidence_band} confidence`}
          </Badge>
        </div>
        {reasoning && reasoning.length > 0 && (
          <div className="mt-3 rounded-xl bg-[#0a1628]/70 border border-[#1e3a5f] px-3.5 py-2.5 text-xs font-mono text-[#e6f0ff]">
            Policy trace: {reasoning.join(" · ")}
          </div>
        )}
        <div
          className={`mt-4 rounded-xl border p-3 flex gap-2.5 ${
            decision === "PASS"
              ? "bg-[#0a1628]/60 border-[#38bdf8]/15"
              : decision === "NO_PATTERN_DETECTED"
              ? "bg-[#1e293b]/60 border-[#64748b]/20"
              : "bg-[#ef4444]/5 border-[#ef4444]/15"
          }`}
        >
          <ShieldAlert
            className={`h-4 w-4 flex-shrink-0 mt-0.5 ${
              decision === "PASS"
                ? "text-[#38bdf8]"
                : decision === "NO_PATTERN_DETECTED"
                ? "text-[#94a3b8]"
                : "text-[#ef4444]"
            }`}
          />
          <p
            className={`text-xs leading-relaxed ${
              decision === "PASS"
                ? "text-[#8aa0c0]"
                : decision === "NO_PATTERN_DETECTED"
                ? "text-[#cbd5e1]"
                : "text-[#fca5a5]"
            }`}
          >
            {s.safety}
          </p>
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm">
          <span className="text-[#8aa0c0]">Human approval required:</span>
          <span
            className={`font-medium ${
              decision === "NO_PATTERN_DETECTED"
                ? "text-[#94a3b8]"
                : human_approval_required
                ? "text-[#f59e0b]"
                : "text-[#38bdf8]"
            }`}
          >
            {decision === "NO_PATTERN_DETECTED"
              ? "Yes — retake with pattern visible"
              : human_approval_required
              ? water
                ? "Yes — do not drink without treatment"
                : "Yes — human verification required"
              : "No"}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function JobPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [result, setResult] = useState<InspectionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollElapsed, setPollElapsed] = useState(0);

  const secondInputRef = useRef<HTMLInputElement>(null);
  const secondVideoRef = useRef<HTMLVideoElement>(null);
  const secondCanvasRef = useRef<HTMLCanvasElement>(null);
  const [secondFile, setSecondFile] = useState<File | null>(null);
  const [secondPreview, setSecondPreview] = useState<string | null>(null);
  const [secondLighting, setSecondLighting] = useState<string>("backlight");
  const [secondUploading, setSecondUploading] = useState(false);
  const [secondMode, setSecondMode] = useState<"idle" | "camera">("idle");
  const [secondError, setSecondError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let elapsedTimer: ReturnType<typeof setInterval> | null = null;
    let timeoutTimer: ReturnType<typeof setTimeout> | null = null;
    let attempts = 0;
    const maxAttempts = 20;
    const fetchJob = async () => {
      try {
        const r = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
        if (!r.ok) throw new Error("Job not found");
        const data = await r.json();
        if (cancelled) return;
        const status = (data as any).status;
        if (status === "processing") {
          setPolling(true);
          attempts += 1;
          if (attempts >= maxAttempts) {
            setError("Inspection is taking longer than expected. Please try again.");
            setPolling(false);
            setLoading(false);
            if (pollTimer) clearInterval(pollTimer);
            if (elapsedTimer) clearInterval(elapsedTimer);
            return;
          }
          return;
        }
        setResult(data);
        setPolling(false);
        setLoading(false);
        if (pollTimer) clearInterval(pollTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);
        if (timeoutTimer) clearTimeout(timeoutTimer);
        try {
          const decision = (data as InspectionResult).final_decision?.decision || "UNKNOWN";
          saveToHistory({ job_id: id, timestamp: new Date().toISOString(), decision, thumbnail_url: null });
        } catch {}
      } catch (e: unknown) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "Failed to load job";
        setError(msg);
        setLoading(false);
        setPolling(false);
        if (pollTimer) clearInterval(pollTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);
      }
    };
    fetchJob();
    pollTimer = setInterval(() => {
      if (polling || loading) fetchJob();
    }, 1500);
    elapsedTimer = setInterval(() => setPollElapsed((prev) => prev + 0.1), 100);
    timeoutTimer = setTimeout(() => {
      if (!cancelled && (polling || loading) && !result) {
        setError("Inspection timed out after 30s. Please try again.");
        setPolling(false);
        setLoading(false);
        if (pollTimer) clearInterval(pollTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);
      }
    }, 30000);
    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      if (elapsedTimer) clearInterval(elapsedTimer);
      if (timeoutTimer) clearTimeout(timeoutTimer);
    };
  }, [id]);

  const copyTrace = useCallback(async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
      toast.success("Trace copied to clipboard");
    } catch {
      toast.error("Failed to copy");
    }
  }, [result]);

  const shareLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success("Link copied to clipboard");
    } catch {
      toast.error("Failed to copy link");
    }
  }, []);

  const downloadReport = useCallback(() => {
    if (!result) return;
    try {
      const doc = new jsPDF();
      const now = new Date().toLocaleString();
      doc.setFontSize(16);
      doc.text("LoopSight v2 — Active-Perception Inspection Report", 14, 20);
      doc.setFontSize(10);
      doc.setTextColor(90);
      doc.text(`Job ID: ${id} | Profile: ${result.inspection_profile || "water_turbidity_v1"}`, 14, 28);
      doc.text(`Generated: ${now} | First-Pass Status: ${result.status}`, 14, 34);
      doc.setTextColor(0);
      doc.setFontSize(12);
      doc.text("1. First-Pass OpenCV 5 Telemetry", 14, 45);
      doc.setFontSize(9);
      let yPos = 52;
      result.regions.forEach((r, i) => {
        const ev = r.evidence;
        const line1 = `Region ${i + 1} (${r.x},${r.y} ${r.w}x${r.h}): edge=${ev.edge_continuity.toFixed(3)} contrast=${(ev.local_contrast ?? 0).toFixed(3)} glare=${((ev.glare_ratio ?? 0) * 100).toFixed(1)}%`;
        const line2 =
          ev.pattern_visibility !== undefined
            ? `  Water Nephelometry: pattern_visibility=${ev.pattern_visibility.toFixed(3)} sharpness=${(ev.pattern_sharpness ?? 0).toFixed(3)} strat_delta=${(ev.stratification_delta ?? 0).toFixed(3)}`
            : ev.crack_width_mm !== undefined
            ? `  Crack Metrology: width=${ev.crack_width_mm.toFixed(3)}mm length=${(ev.crack_length_px ?? 0).toFixed(1)}px severity=${(ev.crack_severity_score ?? 0).toFixed(3)}`
            : "";
        doc.text(line1, 14, yPos);
        yPos += 6;
        if (line2) {
          doc.text(line2, 14, yPos);
          yPos += 6;
        }
      });
      if (result.evidence_gap.length) {
        const gapLines = doc.splitTextToSize(`Evidence gap: ${result.evidence_gap.join("; ")}`, 180);
        doc.text(gapLines, 14, yPos);
        yPos += gapLines.length * 5 + 3;
      }
      if (result.agent_call) {
        doc.text(`2. Bounded Agent Tool Call: ${result.agent_call.tool} (${result.agent_call.reason_code})`, 14, yPos);
        yPos += 7;
      }
      if (result.second_pass) {
        doc.text("3. Second-Pass Metrology Evidence:", 14, yPos);
        yPos += 6;
        result.second_pass.regions.forEach((r, i) => {
          const spLines = doc.splitTextToSize(`  Region ${i + 1}: ${JSON.stringify(r)}`, 180);
          doc.text(spLines, 14, yPos);
          yPos += spLines.length * 5 + 2;
        });
      }
      yPos += 4;
      doc.setFontSize(12);
      doc.text(
        `4. Final Deterministic Verdict: ${result.final_decision.decision} (${result.final_decision.confidence_band})`,
        14,
        yPos
      );
      yPos += 7;
      doc.setFontSize(9);
      doc.text(`Human approval required: ${result.final_decision.human_approval_required ? "Yes" : "No"}`, 14, yPos);
      doc.setFontSize(8);
      doc.setTextColor(120);
      doc.text(
        "Safety: No visible turbidity does NOT confirm safe water — invisible contaminants require a real water test. Visible turbidity: do not drink without treatment.",
        14,
        275
      );
      doc.text("Generated by LoopSight v2 — OpenCV 5 Active-Perception Engine", 14, 283);
      doc.save(`loopsight-${id}.pdf`);
      toast.success("Report downloaded");
    } catch {
      toast.error("Failed to generate PDF");
    }
  }, [result, id]);

  const handleSecondFileSelect = useCallback((file: File) => {
    setSecondFile(file);
    const url = URL.createObjectURL(file);
    setSecondPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return url;
    });
    setSecondError(null);
  }, []);

  const handleSecondInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) handleSecondFileSelect(f);
      e.target.value = "";
    },
    [handleSecondFileSelect]
  );

  const startSecondCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      if (secondVideoRef.current) {
        secondVideoRef.current.srcObject = stream;
        secondVideoRef.current.play();
      }
      setSecondMode("camera");
      setSecondError(null);
    } catch {
      setSecondError("Camera access denied or unavailable.");
    }
  }, []);

  const captureSecond = useCallback(() => {
    if (!secondVideoRef.current || !secondCanvasRef.current) return;
    const v = secondVideoRef.current;
    const c = secondCanvasRef.current;
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    const ctx = c.getContext("2d")!;
    ctx.drawImage(v, 0, 0);
    c.toBlob(
      (blob) => {
        if (blob) handleSecondFileSelect(new File([blob], "capture2.jpg", { type: "image/jpeg" }));
      },
      "image/jpeg",
      0.9
    );
    (v.srcObject as MediaStream)?.getTracks().forEach((t) => t.stop());
    setSecondMode("idle");
  }, [handleSecondFileSelect]);

  const stopSecondCamera = useCallback(() => {
    (secondVideoRef.current?.srcObject as MediaStream)?.getTracks().forEach((t) => t.stop());
    setSecondMode("idle");
  }, []);

  const resetSecond = useCallback(() => {
    if (secondPreview) URL.revokeObjectURL(secondPreview);
    setSecondPreview(null);
    setSecondFile(null);
    setSecondMode("idle");
    setSecondError(null);
  }, [secondPreview]);

  const handleSecondSubmit = useCallback(async () => {
    if (!secondFile || !result) return;
    setSecondUploading(true);
    setSecondError(null);
    try {
      const form = new FormData();
      form.append("original_job_id", id);
      form.append("image", secondFile);
      form.append("lighting2", secondLighting);
      const isWater = isWaterResult(result);
      form.append("inspection_profile", isWater ? "water_turbidity_v1" : result.inspection_profile || "fdm_print_surface_v1");
      const res = await fetch("/api/inspect", { method: "POST", body: form });
      if (!res.ok) throw new Error("Second look failed");
      const { job_id } = await res.json();
      toast.success("Second lighting submitted — analyzing...");
      router.push(`/job/${job_id}`);
    } catch (e: any) {
      setSecondError(e.message || "Failed to submit second photo.");
      toast.error("Failed to submit second photo.");
      setSecondUploading(false);
    }
  }, [secondFile, secondLighting, result, id, router]);

  if (loading || polling) {
    return (
      <div className="min-h-screen bg-[#0a1628] relative flex flex-col items-center justify-center p-4 overflow-hidden">
        <div className="ripple-bg" aria-hidden>
          <div className="ripple-wave ripple-wave-1" />
          <div className="ripple-wave ripple-wave-2" />
        </div>
        <div className="w-full max-w-md space-y-6 text-center relative z-10">
          <div className="flex flex-col items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-[#38bdf8]/15 border border-[#38bdf8]/30 flex items-center justify-center">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}>
                <RefreshCw className="h-7 w-7 text-[#38bdf8]" />
              </motion.div>
            </div>
            <div>
              <p className="text-white font-medium">Checking water clarity & spatial metrology...</p>
              <p className="text-sm text-[#8aa0c0] mt-1">
                {polling ? `Analyzing pattern visibility · ${pollElapsed.toFixed(1)}s` : "Running OpenCV 5 first pass"}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-[#0a1628] flex flex-col items-center justify-center gap-4 p-4">
        <div className="w-16 h-16 rounded-2xl bg-[#0f2942] border border-[#1e3a5f] flex items-center justify-center">
          <XCircle className="h-8 w-8 text-[#8aa0c0]" />
        </div>
        <p className="text-[#fca5a5] text-center max-w-md">{error || "Job not found"}</p>
        <Link href="/">
          <Button variant="outline">Back to inspection workbench</Button>
        </Link>
      </div>
    );
  }

  const showRef = hasReference(result);
  const water = isWaterResult(result);
  const crack = isCrackResult(result);
  const history = typeof window !== "undefined" ? loadHistory() : [];
  const todayCount = history.filter((h) => {
    const d = new Date(h.timestamp);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  }).length;
  const inspectionIndex = history.findIndex((h) => h.job_id === id);
  const inspectionLabel =
    inspectionIndex >= 0 && todayCount > 0 ? `Inspection ${todayCount - inspectionIndex} of ${todayCount} today` : null;
  const statusVariant =
    result.status === "UNCERTAIN" ? "warning" : result.status === "CONFIDENT_PASS" ? "success" : "destructive";

  const frameInfoText: string | null = (() => {
    if (typeof result.frame_info === "string" && result.frame_info) return result.frame_info;
    if (result.frames && Array.isArray(result.frames) && result.frames[0]?.timestamp) {
      return result.frames.map((f) => `#${f.seq} (${f.lighting}) @ ${f.timestamp}`).join(" → ");
    }
    return null;
  })();

  return (
    <div className="min-h-screen bg-[#0a1628] relative">
      <div className="ripple-bg" aria-hidden>
        <div className="ripple-wave ripple-wave-1" style={{ opacity: 0.025 }} />
        <div className="ripple-wave ripple-wave-2" style={{ opacity: 0.02 }} />
      </div>
      <header className="sticky top-0 z-10 backdrop-blur-xl bg-[#0a1628]/80 border-b border-[#1e3a5f]/60">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#0ea5e9] to-[#38bdf8] flex items-center justify-center">
              <Droplets className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-white hidden sm:inline">LoopSight v2</span>
            <span className="text-xs text-[#8aa0c0] hidden md:inline ml-1">
              {water ? "Water Nephelometry Trace" : crack ? "Crack Metrology Trace" : "Surface QC Trace"}
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs hidden sm:flex border-[#1e3a5f] text-[#8aa0c0]">
              {id}
            </Badge>
            <Link href="/">
              <Button variant="outline" size="sm">
                New check
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-6 md:py-8 space-y-4 relative z-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-white flex items-center gap-2">
              {crack ? <Ruler className="h-5 w-5 text-[#38bdf8]" /> : <Waves className="h-5 w-5 text-[#38bdf8]" />}
              {water ? "Water Clarity & Nephelometry Trace" : crack ? "Structural Crack Metrology Trace" : "Evidence Trace"}
            </h1>
            {inspectionLabel && <p className="text-xs text-[#8aa0c0] mt-1">{inspectionLabel}</p>}
            {frameInfoText && <p className="text-[11px] font-mono text-[#5a7aa0] mt-1">{frameInfoText}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={copyTrace}>
              <Copy className="h-3.5 w-3.5 mr-1.5" />
              Copy JSON
            </Button>
            <Button variant="outline" size="sm" onClick={shareLink}>
              <Share2 className="h-3.5 w-3.5 mr-1.5" />
              Share
            </Button>
            <Button variant="outline" size="sm" onClick={downloadReport}>
              <Download className="h-3.5 w-3.5 mr-1.5" />
              PDF
            </Button>
          </div>
        </div>

        {water && (
          <div className="rounded-xl bg-[#38bdf8]/10 border border-[#38bdf8]/15 px-4 py-3 flex gap-2.5">
            <ShieldAlert className="h-4 w-4 text-[#38bdf8] flex-shrink-0 mt-0.5" />
            <p className="text-xs leading-relaxed text-[#8aa0c0]">
              Turbidity is <span className="text-[#e6f0ff] font-medium">not potability</span>. Clear-looking water can
              still carry arsenic, fluoride, or nitrate. This check flags{" "}
              <span className="text-[#38bdf8]">visibly cloudy water</span> — it is not a substitute for a real water
              test.
            </p>
          </div>
        )}

        {/* Section 1: First-Pass Perception */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <Card className="border-[#1e3a5f]/50">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#38bdf8]/15 border border-[#38bdf8]/20 flex items-center justify-center">
                    {water ? <Droplets className="h-3.5 w-3.5 text-[#38bdf8]" /> : <Eye className="h-3.5 w-3.5 text-[#38bdf8]" />}
                  </span>
                  1. Perception (OpenCV 5 First Pass)
                  <span className="text-xs font-normal text-[#8aa0c0]">
                    {result.inspection_profile || "water_turbidity_v1"}
                  </span>
                </CardTitle>
                <Badge variant={statusVariant as any}>{result.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {result.overlay_data_url && (
                <div className="rounded-2xl bg-[#0a1628] border border-[#1e3a5f] p-3 flex flex-col sm:flex-row items-center gap-4">
                  <img
                    src={result.overlay_data_url}
                    alt="Annotated OpenCV 5 Diagnostic Overlay"
                    className="w-36 h-36 object-contain rounded-xl border border-[#1e3a5f]"
                  />
                  <div className="space-y-1 text-xs">
                    <p className="font-semibold text-white flex items-center gap-1.5">
                      <Cpu className="h-3.5 w-3.5 text-[#38bdf8]" />
                      Annotated OpenCV 5 Telemetry Overlay
                    </p>
                    <p className="text-[#8aa0c0] leading-relaxed">
                      Shows canonical ROI boundary, detected specular reflection contours (magenta), 3-zone vertical
                      stratification dividers (amber), or fracture ridge masks (red).
                    </p>
                  </div>
                </div>
              )}

              {result.evidence_gap.length > 0 && (
                <div className="rounded-xl bg-[#f59e0b]/10 border border-[#f59e0b]/20 p-3">
                  <p className="text-xs font-medium text-[#f59e0b] mb-1.5 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    First-pass evidence gap (triggers bounded agent)
                  </p>
                  <ul className="list-disc list-inside text-sm text-[#fcd34d] space-y-0.5">
                    {result.evidence_gap.map((gap, i) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>
                </div>
              )}

              {result.regions.map((region, i) => {
                const ev = region.evidence;
                const pv = ev.pattern_visibility;
                const waterRegion = water || pv !== undefined;
                return (
                  <div key={i} className="rounded-2xl bg-[#0a1628] border border-[#1e3a5f]/50 p-4">
                    <p className="text-xs text-[#5a7aa0] mb-3 font-mono">
                      Region ({region.x}, {region.y}) × {region.w}×{region.h}
                      {ev.detection_method ? ` · method: ${ev.detection_method}` : ""}
                      {ev.pattern_found !== undefined ? ` · pattern ${ev.pattern_found ? "found" : "not found"}` : ""}
                    </p>
                    {crack ? (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                        <div className="p-3 rounded-xl bg-[#0f2942]/60 border border-[#1e3a5f]">
                          <p className="text-[#8aa0c0] text-[11px] uppercase">Crack Width</p>
                          <p className="font-mono font-bold text-white text-lg mt-1">
                            {(ev.crack_width_mm ?? 0).toFixed(3)} mm
                          </p>
                          <p className="text-[10px] text-[#8aa0c0]">Fail ≥ 0.400 mm</p>
                        </div>
                        <div className="p-3 rounded-xl bg-[#0f2942]/60 border border-[#1e3a5f]">
                          <p className="text-[#8aa0c0] text-[11px] uppercase">Fracture Span</p>
                          <p className="font-mono font-bold text-white text-lg mt-1">
                            {(ev.crack_length_px ?? 0).toFixed(1)} px
                          </p>
                          <p className="text-[10px] text-[#8aa0c0]">Connected ridge</p>
                        </div>
                        <div className="p-3 rounded-xl bg-[#0f2942]/60 border border-[#1e3a5f]">
                          <p className="text-[#8aa0c0] text-[11px] uppercase">Severity Score</p>
                          <p className="font-mono font-bold text-[#38bdf8] text-lg mt-1">
                            {(ev.crack_severity_score ?? 0).toFixed(3)}
                          </p>
                          <p className="text-[10px] text-[#8aa0c0]">0..1 normalized</p>
                        </div>
                        <div className="p-3 rounded-xl bg-[#0f2942]/60 border border-[#1e3a5f]">
                          <p className="text-[#8aa0c0] text-[11px] uppercase">Surface Glare</p>
                          <p className="font-mono font-bold text-[#f59e0b] text-lg mt-1">
                            {((ev.glare_ratio ?? 0) * 100).toFixed(1)}%
                          </p>
                          <p className="text-[10px] text-[#8aa0c0]">HSV specular mask</p>
                        </div>
                      </div>
                    ) : waterRegion ? (
                      <div className="space-y-4">
                        <div className="flex flex-wrap gap-6 justify-center py-2">
                          <ClarityGauge value={pv ?? 0} label="Pattern visibility" sublabel="clarity through water" />
                          <div className="grid grid-cols-2 gap-3 min-w-[240px]">
                            <div className="p-2.5 rounded-xl bg-[#0f2942]/50 border border-[#1e3a5f]">
                              <p className="text-[#8aa0c0] text-[11px] uppercase">Sharpness</p>
                              <p className="font-mono font-semibold text-white text-sm mt-0.5">
                                {(ev.pattern_sharpness ?? 0).toFixed(3)}
                              </p>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#0f2942]/50 border border-[#1e3a5f]">
                              <p className="text-[#8aa0c0] text-[11px] uppercase">Local Contrast</p>
                              <p className="font-mono font-semibold text-white text-sm mt-0.5">
                                {(ev.local_contrast ?? ev.edge_continuity ?? 0).toFixed(3)}
                              </p>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#0f2942]/50 border border-[#1e3a5f]">
                              <p className="text-[#8aa0c0] text-[11px] uppercase">Specular Glare</p>
                              <p className="font-mono font-semibold text-[#f59e0b] text-sm mt-0.5">
                                {((ev.glare_ratio ?? 0) * 100).toFixed(1)}%
                              </p>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#0f2942]/50 border border-[#1e3a5f]">
                              <p className="text-[#8aa0c0] text-[11px] uppercase">Stratification Δ</p>
                              <p className="font-mono font-semibold text-[#38bdf8] text-sm mt-0.5">
                                {(ev.stratification_delta ?? 0).toFixed(3)}
                              </p>
                            </div>
                          </div>
                        </div>
                        <ClarityBar value={pv ?? 0} />
                      </div>
                    ) : (
                      <div className={`grid gap-4 text-sm ${showRef ? "grid-cols-3" : "grid-cols-2"}`}>
                        <div>
                          <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Edge continuity</p>
                          <p className="font-mono font-semibold text-white text-base mt-1">
                            {region.evidence.edge_continuity.toFixed(3)}
                          </p>
                        </div>
                        {showRef && (
                          <div>
                            <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Ref. similarity</p>
                            <p className="font-mono font-semibold text-white text-base mt-1">
                              {region.evidence.reference_similarity.toFixed(3)}
                            </p>
                          </div>
                        )}
                        <div>
                          <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Layer align. dev.</p>
                          <p className="font-mono font-semibold text-white text-base mt-1">
                            {region.evidence.layer_alignment_deviation.toFixed(3)}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </motion.div>

        {result.agent_call && (
          <div className="flex justify-center -my-1">
            <div className="flex flex-col items-center gap-1">
              <div className="w-px h-6 bg-gradient-to-b from-[#38bdf8]/50 to-[#38bdf8]/10" />
              <div className="w-6 h-6 rounded-full bg-[#38bdf8]/15 border border-[#38bdf8]/30 flex items-center justify-center">
                <ArrowDown className="h-3 w-3 text-[#7dd3fc]" />
              </div>
            </div>
          </div>
        )}

        {/* Section 2: Bounded Agent Decision */}
        {result.agent_call && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.15 }}>
            <Card className="border-[#38bdf8]/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#38bdf8]/15 border border-[#38bdf8]/30 flex items-center justify-center">
                    <Sun className="h-3.5 w-3.5 text-[#38bdf8]" />
                  </span>
                  2. Bounded Agent Tool Selection (MCP Active Perception)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-xl bg-[#38bdf8]/10 border border-[#38bdf8]/20 p-4">
                  <p className="text-xs uppercase tracking-widest text-[#38bdf8] mb-3">Whitelisted OpenCV 5 Tool Call</p>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="inline-flex items-center px-3 py-1.5 rounded-xl bg-[#0a1628] border border-[#1e3a5f] font-mono text-sm text-[#e6f0ff]">
                      {result.agent_call.tool}
                    </span>
                    <span className="text-[#5a7aa0]">→</span>
                    <span className="text-sm text-[#8aa0c0]">
                      reason_code:{" "}
                      <span className="font-mono text-[#e6f0ff] bg-[#0f2942] px-2 py-1 rounded-lg border border-[#1e3a5f]">
                        {result.agent_call.reason_code}
                      </span>
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Section 3: Second-Pass Evidence */}
        {result.second_pass && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
            <Card className="border-[#22c55e]/25">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#22c55e]/15 border border-[#22c55e]/20 flex items-center justify-center">
                    <Eye className="h-3.5 w-3.5 text-[#22c55e]" />
                  </span>
                  3. Second-Pass Metrology Evidence
                  <span className="text-xs font-normal text-[#8aa0c0]">
                    After executing {result.agent_call?.tool || "second-look tool"}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.second_pass.notes && (
                  <div className="rounded-xl bg-[#0f2942]/70 border border-[#1e3a5f] px-3.5 py-2.5 text-xs font-mono text-[#7dd3fc]">
                    Tool execution note: {result.second_pass.notes}
                  </div>
                )}
                {result.second_pass.regions.map((region, i) => {
                  const pv = region.pattern_visibility;
                  const waterSec = water && pv !== undefined;
                  return (
                    <div key={i} className="rounded-xl bg-[#0a1628] border border-[#1e3a5f]/50 p-4">
                      {waterSec ? (
                        <div className="space-y-3">
                          <div className="flex flex-wrap gap-6 items-center justify-center">
                            <ClarityGauge value={pv ?? region.edge_continuity} label="Second-Look Visibility" />
                            <div className="text-sm space-y-1.5">
                              {Object.entries(region).map(([key, val]) => {
                                if (key === "pattern_visibility") return null;
                                if (typeof val === "number" && val < 0) return null;
                                if (key === "reference_similarity" && !showRef) return null;
                                return (
                                  <div key={key} className="flex gap-2">
                                    <span className="text-[#8aa0c0] text-xs uppercase">{key.replace(/_/g, " ")}:</span>
                                    <span className="font-mono text-white text-xs">
                                      {typeof val === "number" ? val.toFixed(3) : String(val)}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                          <ClarityBar value={pv ?? region.edge_continuity} />
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          {Object.entries(region).map(([key, val]) => {
                            if (key === "reference_similarity" && !showRef) return null;
                            if (typeof val === "number" && val < 0) return null;
                            return (
                              <div key={key}>
                                <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">{key.replace(/_/g, " ")}</p>
                                <p className="font-mono font-semibold text-white mt-1">
                                  {typeof val === "number" ? val.toFixed(3) : String(val)}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Interactive Second-Lighting Capture Card when UNCERTAIN */}
        {water && result.status === "UNCERTAIN" && (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="w-full">
            <Card className="border-2 border-[#f59e0b]/40 bg-gradient-to-br from-[#0f2942] via-[#0f2942] to-[#1a365d]/80 overflow-hidden">
              <div className="h-1 w-full bg-gradient-to-r from-[#f59e0b] via-[#38bdf8] to-[#0ea5e9]" />
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <span className="w-10 h-10 rounded-xl bg-[#f59e0b] flex items-center justify-center shadow-lg shadow-[#f59e0b]/30">
                    <Sun className="h-5 w-5 text-white" />
                  </span>
                  <div>
                    <CardTitle className="text-[15px] text-white">
                      Optional: Supply a Second Photo Under Different Lighting
                    </CardTitle>
                    <p className="text-xs text-[#f59e0b] font-medium">
                      Runs multi-frame registration & persistence via track_across_frames([frame1, frame2])
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {secondError && (
                  <div className="rounded-xl bg-[#ef4444]/10 border border-[#ef4444]/20 p-3 text-xs text-[#fca5a5]">
                    {secondError}
                  </div>
                )}
                <div className="flex gap-2">
                  <select
                    value={secondLighting}
                    onChange={(e) => setSecondLighting(e.target.value)}
                    className="h-10 rounded-xl border border-[#1e3a5f] bg-[#0a1628] text-[#e6f0ff] text-sm px-3 flex-1"
                  >
                    <option value="backlight">Backlight (behind glass)</option>
                    <option value="ambient">Ambient light</option>
                    <option value="flash">Phone flash</option>
                  </select>
                  <Button variant="outline" size="sm" onClick={() => secondInputRef.current?.click()} className="h-10">
                    <Upload className="h-4 w-4 mr-1.5" />
                    Upload 2nd
                  </Button>
                  <Button variant="outline" size="sm" onClick={startSecondCamera} className="h-10">
                    <Camera className="h-4 w-4 mr-1.5" />
                    Camera
                  </Button>
                </div>
                <input ref={secondInputRef} type="file" accept="image/*" className="hidden" onChange={handleSecondInput} />
                {secondMode === "camera" && (
                  <div className="space-y-2">
                    <div className="rounded-xl overflow-hidden border border-[#1e3a5f] bg-black">
                      <video ref={secondVideoRef} className="w-full max-h-64 object-contain" autoPlay playsInline muted />
                    </div>
                    <div className="flex gap-2">
                      <Button onClick={captureSecond} className="flex-1 bg-[#38bdf8] text-[#0a1628] font-semibold">
                        Capture second
                      </Button>
                      <Button onClick={stopSecondCamera} variant="outline" className="flex-1">
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
                {secondPreview && (
                  <div className="relative rounded-xl overflow-hidden border border-[#1e3a5f]/60 bg-[#0a1628]">
                    <img src={secondPreview} alt="Second lighting" className="w-full max-h-64 object-contain mx-auto" />
                    <button
                      onClick={resetSecond}
                      className="absolute top-2 right-2 rounded-full bg-black/60 p-2 text-white hover:bg-black/80"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}
                <Button
                  onClick={handleSecondSubmit}
                  disabled={!secondFile || secondUploading}
                  className="w-full h-11 bg-[#38bdf8] hover:bg-[#0ea5e9] text-[#0a1628] font-semibold disabled:opacity-40"
                >
                  {secondUploading ? "Analyzing both frames..." : "Submit second lighting → re-inspect with both frames"}
                </Button>
                <canvas ref={secondCanvasRef} className="hidden" />
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Side-by-side LOOK 1 vs LOOK 2 when two frames were used */}
        {water && result.frames && result.frames.length === 2 && result.second_pass && (
          <Card className="border-2 border-[#38bdf8]/30 bg-[#0a1628]/80 overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Eye className="h-4 w-4 text-[#38bdf8]" />
                LOOK 1 vs LOOK 2 — Multi-Lighting Active-Perception Comparison
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {(() => {
                const f1vis = result.regions[0]?.evidence?.pattern_visibility ?? 0;
                const f2vis =
                  result.second_pass?.regions[0]?.pattern_visibility ??
                  result.second_pass?.regions[0]?.edge_continuity ??
                  0;
                const delta = f2vis - f1vis;
                const f1 = result.frames[0];
                const f2 = result.frames[1];
                return (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
                    <div className="rounded-xl bg-[#0f2942] border border-[#1e3a5f] p-4 text-center">
                      <p className="text-xs font-mono text-[#8aa0c0]">LOOK 1 ({f1.lighting})</p>
                      <p className="text-2xl font-bold font-mono text-white mt-1">{f1vis.toFixed(3)}</p>
                    </div>
                    <div className="rounded-xl bg-[#0a1628] border border-[#38bdf8]/40 p-4 text-center">
                      <p className="text-xs font-mono text-[#38bdf8]">Evidence Delta (Δ)</p>
                      <p className="text-2xl font-bold font-mono text-[#38bdf8] mt-1">
                        {delta >= 0 ? `+${delta.toFixed(3)}` : delta.toFixed(3)}
                      </p>
                    </div>
                    <div className="rounded-xl bg-[#0f2942] border border-[#1e3a5f] p-4 text-center">
                      <p className="text-xs font-mono text-[#8aa0c0]">LOOK 2 ({f2.lighting})</p>
                      <p className="text-2xl font-bold font-mono text-[#38bdf8] mt-1">{f2vis.toFixed(3)}</p>
                    </div>
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        )}

        {/* Section 4: Final Decision */}
        <DecisionCard result={result} />

        {/* Section 5: Stage Timing Telemetry */}
        {result.measurements && (
          <Card className="border-[#1e3a5f]/50">
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-widest text-[#8aa0c0] mb-2.5">
                Stage Latency Telemetry (ms)
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono">
                <div className="p-2 rounded-lg bg-[#0a1628] border border-[#1e3a5f]">
                  <span className="text-[#8aa0c0] block">decode</span>
                  <span className="text-white">{result.measurements.decode_ms ?? "—"} ms</span>
                </div>
                <div className="p-2 rounded-lg bg-[#0a1628] border border-[#1e3a5f]">
                  <span className="text-[#8aa0c0] block">first_pass</span>
                  <span className="text-white">{result.measurements.first_pass_ms ?? "—"} ms</span>
                </div>
                <div className="p-2 rounded-lg bg-[#0a1628] border border-[#1e3a5f]">
                  <span className="text-[#8aa0c0] block">agent</span>
                  <span className="text-white">{result.measurements.agent_ms ?? "—"} ms</span>
                </div>
                <div className="p-2 rounded-lg bg-[#0a1628] border border-[#1e3a5f]">
                  <span className="text-[#8aa0c0] block">second_pass</span>
                  <span className="text-white">{result.measurements.second_pass_ms ?? "—"} ms</span>
                </div>
                <div className="p-2 rounded-lg bg-[#0a1628] border border-[#38bdf8]/40">
                  <span className="text-[#38bdf8] block">total</span>
                  <span className="text-[#38bdf8] font-bold">{result.measurements.total_ms} ms</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
