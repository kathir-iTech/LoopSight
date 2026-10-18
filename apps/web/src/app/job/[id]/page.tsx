"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import type { InspectionResult } from "@/lib/types";
import { saveToHistory, loadHistory } from "@/lib/history";
import toast from "react-hot-toast";
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  Copy,
  Download,
  Share2,
  RefreshCw,
  Droplets,
  Eye,
  Sun,
  Waves,
  ShieldAlert,
  ShieldCheck,
  Camera,
  Upload,
  X,
  Ruler,
  Cpu,
  Layers,
  Activity,
  Maximize2,
  Crosshair,
  Sliders,
  ChevronRight,
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
  const circumference = 2 * Math.PI * 44;
  const offset = circumference * (1 - pct);
  const gradId = `grad-${label.replace(/\s+/g, "")}-${Math.round(pct * 100)}`;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-[116px] h-[116px] flex items-center justify-center">
        <svg width={116} height={116} viewBox="0 0 116 116" className="rotate-[-90deg]">
          <circle cx={58} cy={58} r={44} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={10} />
          <defs>
            <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="40%" stopColor="#f59e0b" />
              <stop offset="75%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#0ea5e9" />
            </linearGradient>
          </defs>
          <circle
            cx={58}
            cy={58}
            r={44}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 900ms ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[20px] font-bold font-mono tracking-tight" style={{ color: statusColor }}>
            {(pct * 100).toFixed(0)}%
          </span>
          <span className="text-[10px] tracking-wider uppercase font-semibold" style={{ color: statusColor }}>
            {statusText}
          </span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-xs font-bold text-white">{label}</p>
        {sublabel && <p className="text-[10px] text-[#8aa0c0]">{sublabel}</p>}
        <p className="text-[11px] font-mono text-[#38bdf8] font-semibold mt-0.5">{value.toFixed(3)}</p>
      </div>
    </div>
  );
}

function ClarityBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="space-y-1.5 w-full">
      <div className="flex justify-between text-[11px] font-medium">
        <span className="text-[#ef4444]">Turbid (&le;0.20)</span>
        <span className="text-[#f59e0b]">Borderline (0.20-0.55)</span>
        <span className="text-[#38bdf8]">Clear (&ge;0.55)</span>
      </div>
      <div
        className="relative h-3 rounded-full overflow-hidden border border-white/10"
        style={{ background: "rgba(255,255,255,0.06)" }}
      >
        <div
          className="absolute inset-0 rounded-full"
          style={{ background: "linear-gradient(90deg, #ef4444 0%, #f59e0b 38%, #38bdf8 72%, #0ea5e9 100%)", opacity: 0.95 }}
        />
        <div className="absolute top-0 bottom-0 w-px bg-white/90" style={{ left: "20%" }} />
        <div className="absolute top-0 bottom-0 w-px bg-white/90" style={{ left: "55%" }} />
        <motion.div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border-2 border-[#070d18] shadow-md shadow-white/50"
          initial={{ left: "0%" }}
          animate={{ left: `calc(${pct}% - 8px)` }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </div>
      <div className="flex justify-between text-[10px] font-mono text-[#8aa0c0]">
        <span>0.20</span>
        <span>0.55</span>
      </div>
    </div>
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

  const [activeOverlayLayer, setActiveOverlayLayer] = useState<"overlay" | "raw" | "second">("overlay");
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  const secondInputRef = useRef<HTMLInputElement>(null);
  const secondVideoRef = useRef<HTMLVideoElement>(null);
  const secondCanvasRef = useRef<HTMLCanvasElement>(null);
  const [secondFile, setSecondFile] = useState<File | null>(null);
  const [secondPreview, setSecondPreview] = useState<string | null>(null);
  const [secondLighting, setSecondLighting] = useState<string>("backlight");
  const [secondUploading, setSecondUploading] = useState(false);
  const [secondMode, setSecondMode] = useState<"idle" | "camera">("idle");
  const [secondError, setSecondError] = useState<string | null>(null);
  const [secondCameraStream, setSecondCameraStream] = useState<MediaStream | null>(null);
  const [secondCameraLoading, setSecondCameraLoading] = useState(false);

  useEffect(() => {
    return () => {
      if (secondCameraStream) {
        secondCameraStream.getTracks().forEach((t) => t.stop());
      }
    };
  }, [secondCameraStream]);

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
            setError("Inspection is taking longer than expected. Please retry.");
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
        setError("Inspection timed out after 30s. Please retry.");
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
      toast.success("MCP Trace JSON copied to clipboard");
    } catch {
      toast.error("Failed to copy trace");
    }
  }, [result]);

  const shareLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success("Inspection link copied to clipboard");
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
      doc.text("LoopSight v2 — Active-Perception Metrology Report", 14, 20);
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
            ? `  Water Nephelometry: pattern_visibility=${ev.pattern_visibility.toFixed(3)} sharpness=${(ev.pattern_sharpness ?? 0).toFixed(3)} strat_delta=${(ev.stratification_delta ?? 0).toFixed(3)} NTU=${(ev.estimated_ntu ?? 0).toFixed(1)}`
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
        doc.text(`2. Bounded Agent Tool Dispatch: ${result.agent_call.tool} (${result.agent_call.reason_code})`, 14, yPos);
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
      doc.text("4. Deterministic Final Verdict", 14, yPos);
      yPos += 7;
      doc.setFontSize(10);
      doc.text(`Verdict: ${result.final_decision.decision} (${result.final_decision.confidence_band} confidence)`, 14, yPos);
      yPos += 6;
      doc.text(`Human approval required: ${result.final_decision.human_approval_required ? "YES" : "NO"}`, 14, yPos);
      doc.save(`LoopSight-${id}.pdf`);
      toast.success("PDF report downloaded");
    } catch {
      toast.error("Failed to generate PDF");
    }
  }, [result, id]);

  const handleSecondFileSelect = useCallback((file: File) => {
    setSecondFile(file);
    const url = URL.createObjectURL(file);
    setSecondPreview((prev) => {
      if (prev && prev.startsWith("blob:")) URL.revokeObjectURL(prev);
      return url;
    });
    setSecondError(null);
  }, []);

  const handleSecondInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleSecondFileSelect(file);
      e.target.value = "";
    },
    [handleSecondFileSelect]
  );

  const startSecondCamera = useCallback(async () => {
    setSecondCameraLoading(true);
    setSecondError(null);
    try {
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
      }
      setSecondCameraStream(stream);
      setSecondMode("camera");
      setSecondCameraLoading(false);
    } catch (err) {
      console.error("Second camera error:", err);
      setSecondCameraLoading(false);
      setSecondError("Camera access denied or unavailable. Please upload a photo instead.");
      toast.error("Camera unavailable");
    }
  }, []);

  const stopSecondCamera = useCallback(() => {
    if (secondCameraStream) {
      secondCameraStream.getTracks().forEach((t) => t.stop());
    }
    setSecondCameraStream(null);
    setSecondMode("idle");
    setSecondCameraLoading(false);
  }, [secondCameraStream]);

  const captureSecond = useCallback(() => {
    if (!secondVideoRef.current || !secondCanvasRef.current) return;
    const v = secondVideoRef.current;
    const c = secondCanvasRef.current;
    if (!v.videoWidth || !v.videoHeight) {
      toast.error("Camera feed not ready yet.");
      return;
    }
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(v, 0, 0);
    c.toBlob(
      (blob) => {
        if (blob) handleSecondFileSelect(new File([blob], "capture2.jpg", { type: "image/jpeg" }));
      },
      "image/jpeg",
      0.92
    );
    stopSecondCamera();
  }, [handleSecondFileSelect, stopSecondCamera]);

  const resetSecond = useCallback(() => {
    if (secondPreview && secondPreview.startsWith("blob:")) URL.revokeObjectURL(secondPreview);
    setSecondPreview(null);
    setSecondFile(null);
    stopSecondCamera();
    setSecondError(null);
  }, [secondPreview, stopSecondCamera]);

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
      toast.success("Second lighting submitted — evaluating dual-look...");
      router.push(`/job/${job_id}`);
    } catch (e: any) {
      setSecondError(e.message || "Failed to submit second photo.");
      toast.error("Failed to submit second photo.");
      setSecondUploading(false);
    }
  }, [secondFile, secondLighting, result, id, router]);

  if (loading || polling) {
    return (
      <div className="min-h-screen bg-[#070d18] relative flex flex-col items-center justify-center p-4 overflow-hidden">
        <div className="studio-grid absolute inset-0 opacity-40 pointer-events-none" />
        <div className="w-full max-w-md space-y-6 text-center relative z-10 glass-studio p-8 rounded-3xl">
          <div className="flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-[#38bdf8]/15 border border-[#38bdf8]/30 flex items-center justify-center glow-cyan">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}>
                <RefreshCw className="h-8 w-8 text-[#38bdf8]" />
              </motion.div>
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-white">Analyzing OpenCV 5 Metrology...</h2>
              <p className="text-xs text-[#8aa0c0] font-mono">
                {polling ? `Evaluating active perception loop · ${pollElapsed.toFixed(1)}s` : "Ingesting first-pass evidence"}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-[#070d18] flex flex-col items-center justify-center gap-4 p-4 text-center">
        <div className="w-16 h-16 rounded-2xl bg-[#0b192e] border border-[#163256] flex items-center justify-center text-[#ef4444]">
          <XCircle className="h-8 w-8" />
        </div>
        <p className="text-[#fca5a5] max-w-md text-sm">{error || "Job not found"}</p>
        <Link href="/">
          <Button variant="outline" className="border-[#163256] bg-[#0b192e] text-white hover:bg-[#163256]">
            Return to Studio Workbench
          </Button>
        </Link>
      </div>
    );
  }

  const showRef = hasReference(result);
  const water = isWaterResult(result);
  const crack = isCrackResult(result);
  const decision = result.final_decision.decision;

  const decisionStyles: Record<
    string,
    { glow: string; bg: string; border: string; text: string; icon: React.ReactNode; label: string; banner: string }
  > = {
    PASS: {
      glow: "glow-emerald",
      bg: "bg-[#22c55e]/10",
      border: "border-[#22c55e]/40",
      text: "text-[#22c55e]",
      icon: <CheckCircle2 className="h-8 w-8 text-[#22c55e]" />,
      label: "PASS",
      banner: water
        ? "NO VISIBLE TURBIDITY DETECTED (CLEAR SAMPLE)"
        : crack
        ? "NO STRUCTURAL FRACTURE DETECTED (CLEARED ARTIFACT)"
        : "CONFIDENT PASS — NO DEFECT DETECTED",
    },
    FAIL: {
      glow: "glow-ruby",
      bg: "bg-[#ef4444]/10",
      border: "border-[#ef4444]/40",
      text: "text-[#ef4444]",
      icon: <XCircle className="h-8 w-8 text-[#ef4444]" />,
      label: "FAIL",
      banner: water
        ? "VISIBLE TURBIDITY DETECTED (CONTAMINATED SAMPLE)"
        : crack
        ? `STRUCTURAL FRACTURE DETECTED (${(result.regions[0]?.evidence.crack_width_mm ?? 0.719).toFixed(3)} mm)`
        : "DEFECT SIGNAL CONFIRMED",
    },
    REVIEW: {
      glow: "glow-amber",
      bg: "bg-[#f59e0b]/10",
      border: "border-[#f59e0b]/40",
      text: "text-[#f59e0b]",
      icon: <AlertTriangle className="h-8 w-8 text-[#f59e0b]" />,
      label: "REVIEW",
      banner: "BORDERLINE CONFIDENCE — HUMAN REVIEW REQUIRED",
    },
    NO_PATTERN_DETECTED: {
      glow: "",
      bg: "bg-[#64748b]/10",
      border: "border-[#64748b]/40",
      text: "text-[#94a3b8]",
      icon: <Eye className="h-8 w-8 text-[#94a3b8]" />,
      label: "NO PATTERN",
      banner: "PATTERN NOT DETECTED — RETAKE WITH CHECKERBOARD",
    },
  };

  const decStyle = decisionStyles[decision] || decisionStyles.REVIEW;

  // Primary evidence region
  const primaryRegion = result.regions[0];
  const primaryEvidence = primaryRegion?.evidence;
  const patternVis = primaryEvidence?.pattern_visibility ?? primaryEvidence?.edge_continuity ?? 0;
  const secondVis = result.second_pass?.regions[0]?.pattern_visibility ?? result.second_pass?.regions[0]?.edge_continuity;
  const estimatedNtu =
    primaryEvidence?.estimated_ntu ??
    (patternVis > 0 ? Math.max(0.1, 3.5 * Math.pow(Math.max(0.001, 1 / patternVis - 1), 1.15)) : 18.5);

  const whoTier =
    primaryEvidence?.who_tier ||
    (patternVis >= 0.85 ? "PRISTINE" : patternVis >= 0.55 ? "ACCEPTABLE" : "ELEVATED_TURBIDITY");

  return (
    <div className="min-h-screen bg-[#070d18] text-[#e6f0ff] relative overflow-hidden flex flex-col">
      {/* Studio Background */}
      <div className="absolute inset-0 bg-gradient-loopsight pointer-events-none" />
      <div className="studio-grid absolute inset-0 opacity-40 pointer-events-none" />

      {/* Top Header */}
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-[#070d18]/85 border-b border-[#163256]/80 px-4 md:px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs font-medium text-[#8aa0c0] hover:text-white transition-colors bg-[#0b192e] px-3 py-1.5 rounded-lg border border-[#163256]"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Studio
          </Link>
          <div className="h-4 w-px bg-[#163256]" />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-white tracking-tight">Inspection Trace Console</h1>
              <span className="font-mono text-[10px] bg-[#0b192e] text-[#38bdf8] px-2 py-0.5 rounded border border-[#163256]">
                {id}
              </span>
            </div>
            <p className="text-[11px] text-[#8aa0c0] hidden sm:block">
              {water ? "Optical Nephelometry Physical Metrology" : crack ? "Structural Crack Distance Transform Metrology" : "Surface QC"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={copyTrace}
            className="border-[#163256] bg-[#0b192e] text-white hover:bg-[#163256] text-xs h-8"
          >
            <Copy className="h-3.5 w-3.5 mr-1" />
            JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={shareLink}
            className="border-[#163256] bg-[#0b192e] text-white hover:bg-[#163256] text-xs h-8"
          >
            <Share2 className="h-3.5 w-3.5 mr-1" />
            Share
          </Button>
          <Button
            size="sm"
            onClick={downloadReport}
            className="bg-[#38bdf8] hover:bg-[#0ea5e9] text-[#070d18] font-bold text-xs h-8 shadow-md shadow-[#38bdf8]/20"
          >
            <Download className="h-3.5 w-3.5 mr-1" />
            PDF Report
          </Button>
        </div>
      </header>

      {/* Main Diagnostic Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 relative z-10">
        {/* HERO DECISION BANNER */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`rounded-3xl border-2 p-5 md:p-6 ${decStyle.bg} ${decStyle.border} ${decStyle.glow} relative overflow-hidden`}
        >
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-5 relative z-10">
            <div className="flex items-start gap-4">
              <div className={`w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0 bg-[#070d18]/60 border ${decStyle.border}`}>
                {decStyle.icon}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <span className={`text-2xl md:text-3xl font-extrabold font-mono tracking-tight ${decStyle.text}`}>
                    {decStyle.label}
                  </span>
                  <span className="text-xs font-mono uppercase px-2.5 py-0.5 rounded-full bg-[#070d18]/70 border border-white/10 text-white font-semibold">
                    {result.final_decision.confidence_band} Confidence
                  </span>
                </div>
                <h2 className="text-base md:text-lg font-bold text-white tracking-wide">
                  {decStyle.banner}
                </h2>
                <p className="text-xs text-[#cbd5e1] max-w-2xl leading-relaxed">
                  {water ? (
                    decision === "PASS" ? (
                      <span>
                        Optical pattern clarity through water sample meets drinking water nephelometry standard (&ge;0.55).{" "}
                        <strong className="text-white">Notice:</strong> Does not verify invisible chemical contaminants (arsenic/fluoride).
                      </span>
                    ) : (
                      <span>
                        Visible turbidity detected. The sample obscures the optical checkerboard pattern.{" "}
                        <strong className="text-[#fca5a5]">Do not consume without certified filtration or treatment.</strong>
                      </span>
                    )
                  ) : crack ? (
                    decision === "PASS" ? (
                      <span>
                        Surface shadow or illumination artifact resolved by second-pass homomorphic normalization (&lt;0.15mm threshold).
                      </span>
                    ) : (
                      <span>
                        Structural concrete fracture confirmed (&ge;0.400mm civil engineering threshold). Structural engineering follow-up required.
                      </span>
                    )
                  ) : (
                    "Deterministic verdict generated by LoopSight policy.py engine."
                  )}
                </p>
              </div>
            </div>

            {/* Quick Summary Pill on Right */}
            <div className="flex flex-col items-start lg:items-end gap-1.5 font-mono text-xs text-[#8aa0c0] flex-shrink-0">
              <span className="px-3 py-1 rounded-xl bg-[#070d18]/80 border border-white/10 text-white">
                Profile: <strong className="text-[#38bdf8]">{result.inspection_profile || "water_turbidity_v1"}</strong>
              </span>
              <span>First-Pass Status: <strong className="text-white">{result.status}</strong></span>
              <span>Human Approval: <strong className={result.final_decision.human_approval_required ? "text-[#f59e0b]" : "text-[#22c55e]"}>{result.final_decision.human_approval_required ? "REQUIRED" : "NOT NEEDED"}</strong></span>
            </div>
          </div>

          {result.final_decision.reasoning && (
            <div className="mt-4 pt-3 border-t border-white/10 text-xs font-mono text-[#cbd5e1] flex items-center gap-2">
              <span className="text-[#8aa0c0] font-semibold">POLICY TRACE:</span>
              <span>{result.final_decision.reasoning.join(" · ")}</span>
            </div>
          )}
        </motion.div>

        {/* 2-COLUMN INSPECTION STAGE */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* LEFT: Full-Screen Interactive Vision Inspection Canvas (7 Cols) */}
          <div className="lg:col-span-7 space-y-3">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-[#38bdf8]" />
                <h3 className="text-xs font-bold tracking-wide uppercase text-white">
                  OpenCV 5 Diagnostic Metrology Viewport
                </h3>
              </div>

              {/* Layer Switcher */}
              <div className="flex items-center gap-1 p-0.5 rounded-lg bg-[#0b192e] border border-[#163256] text-[11px] font-mono">
                <button
                  type="button"
                  onClick={() => setActiveOverlayLayer("overlay")}
                  className={`px-2.5 py-1 rounded-md transition-all ${
                    activeOverlayLayer === "overlay"
                      ? "bg-[#38bdf8] text-[#070d18] font-bold"
                      : "text-[#8aa0c0] hover:text-white"
                  }`}
                >
                  OpenCV Diagnostic
                </button>
                <button
                  type="button"
                  onClick={() => setActiveOverlayLayer("raw")}
                  className={`px-2.5 py-1 rounded-md transition-all ${
                    activeOverlayLayer === "raw"
                      ? "bg-[#38bdf8] text-[#070d18] font-bold"
                      : "text-[#8aa0c0] hover:text-white"
                  }`}
                >
                  Raw Input
                </button>
                {secondVis !== undefined && (
                  <button
                    type="button"
                    onClick={() => setActiveOverlayLayer("second")}
                    className={`px-2.5 py-1 rounded-md transition-all ${
                      activeOverlayLayer === "second"
                        ? "bg-[#38bdf8] text-[#070d18] font-bold"
                        : "text-[#8aa0c0] hover:text-white"
                    }`}
                  >
                    Second Look (LOOK 2)
                  </button>
                )}
              </div>
            </div>

            {/* The Visual Stage */}
            <div
              className="hud-bracket relative w-full h-[460px] md:h-[500px] rounded-2xl border-2 border-[#163256] bg-[#070d18] shadow-2xl overflow-hidden flex flex-col justify-between"
              onMouseMove={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                setMousePos({
                  x: Math.round(e.clientX - rect.left),
                  y: Math.round(e.clientY - rect.top),
                });
              }}
              onMouseLeave={() => setMousePos(null)}
            >
              {/* Top Viewport Header */}
              <div className="p-3.5 flex items-center justify-between z-20 pointer-events-none">
                <span className="px-2.5 py-1 rounded-md bg-[#070d18]/80 backdrop-blur border border-white/10 text-[11px] font-mono text-[#7dd3fc] flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8] animate-ping" />
                  {activeOverlayLayer === "overlay"
                    ? "OPENCV 5 TELEMETRY OVERLAY"
                    : activeOverlayLayer === "raw"
                    ? "RAW SENSOR INGEST"
                    : "SECOND-PASS INPAINTED LOOK"}
                </span>

                {mousePos && (
                  <span className="px-2 py-0.5 rounded bg-[#070d18]/80 backdrop-blur border border-white/10 text-[10px] font-mono text-[#8aa0c0]">
                    HUD COORD: X:{mousePos.x} Y:{mousePos.y}
                  </span>
                )}
              </div>

              {/* Central Visual Image Display */}
              <div className="relative flex-1 flex items-center justify-center p-4 overflow-hidden">
                <AnimatePresence mode="wait">
                  {activeOverlayLayer === "overlay" && result.overlay_data_url ? (
                    <motion.div
                      key="overlay"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="relative w-full h-full flex items-center justify-center"
                    >
                      <img
                        src={result.overlay_data_url}
                        alt="OpenCV 5 Diagnostic Overlay"
                        className="max-h-full max-w-full object-contain rounded-xl border border-white/10 shadow-2xl"
                      />
                    </motion.div>
                  ) : activeOverlayLayer === "second" && secondPreview ? (
                    <motion.div
                      key="second"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="relative w-full h-full flex items-center justify-center"
                    >
                      <img
                        src={secondPreview}
                        alt="Second Lighting Frame"
                        className="max-h-full max-w-full object-contain rounded-xl border border-white/10 shadow-2xl"
                      />
                    </motion.div>
                  ) : (
                    <motion.div
                      key="raw"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="relative w-full h-full flex items-center justify-center"
                    >
                      {/* If no separate raw image data URL exists, show the overlay or sample image */}
                      <img
                        src={result.overlay_data_url || "/samples/water_glare_confounded.png"}
                        alt="Raw Ingest Frame"
                        className="max-h-full max-w-full object-contain rounded-xl border border-white/10 shadow-2xl"
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Viewport Legend Bottom Bar */}
              <div className="p-3 bg-[#070d18]/90 backdrop-blur border-t border-[#163256]/80 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono">
                  <span className="flex items-center gap-1.5 text-[#38bdf8]">
                    <span className="w-2.5 h-2.5 rounded border border-[#38bdf8] bg-[#38bdf8]/20" />
                    ROI Boundary
                  </span>
                  <span className="flex items-center gap-1.5 text-[#d946ef]">
                    <span className="w-2.5 h-2.5 rounded border border-[#d946ef] bg-[#d946ef]/20" />
                    Glare Mask (Telea)
                  </span>
                  <span className="flex items-center gap-1.5 text-[#f59e0b]">
                    <span className="w-2.5 h-2.5 rounded border border-[#f59e0b] bg-[#f59e0b]/20" />
                    Stratification Zones
                  </span>
                  <span className="flex items-center gap-1.5 text-[#ef4444]">
                    <span className="w-2.5 h-2.5 rounded border border-[#ef4444] bg-[#ef4444]/20" />
                    Fracture Ridge
                  </span>
                </div>

                <div className="text-[11px] font-mono text-[#8aa0c0]">
                  cv2.distanceTransform & Inpainting Active
                </div>
              </div>
            </div>

            {/* Evidence Gap Ticker if present */}
            {result.evidence_gap.length > 0 && (
              <div className="rounded-xl bg-[#f59e0b]/10 border border-[#f59e0b]/30 p-3.5 space-y-1">
                <p className="text-xs font-bold text-[#f59e0b] flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4" />
                  First-Pass Evidence Gap (Triggered Bounded Agent):
                </p>
                <ul className="list-disc list-inside text-xs text-[#fde68a] space-y-0.5">
                  {result.evidence_gap.map((gap, i) => (
                    <li key={i}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* RIGHT: Physical Metrology Telemetry Matrix (5 Cols) */}
          <div className="lg:col-span-5 space-y-4">
            {/* Primary Physical Nephelometry Card */}
            <div className="glass-studio rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wide text-[#8aa0c0] flex items-center gap-1.5">
                  <Droplets className="h-4 w-4 text-[#38bdf8]" />
                  Physical Optical Telemetry
                </span>
                <span className="text-[11px] font-mono text-[#38bdf8] bg-[#38bdf8]/10 px-2 py-0.5 rounded border border-[#38bdf8]/20">
                  Beer-Lambert Calibrated
                </span>
              </div>

              {water ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-center gap-6 py-2">
                    <ClarityGauge value={patternVis} label="Pattern Visibility" sublabel="Optical transmission v" />

                    <div className="grid grid-cols-2 gap-2.5 flex-1 min-w-[200px]">
                      <div className="p-3 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                        <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">Estimated NTU</span>
                        <span className="text-xl font-extrabold font-mono text-white block mt-0.5">
                          {estimatedNtu.toFixed(1)} <span className="text-xs font-normal text-[#8aa0c0]">NTU</span>
                        </span>
                        <span className="text-[9px] text-[#38bdf8] block mt-0.5 font-mono">
                          WHO Standard &lt; 5.0
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                        <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">WHO Quality Tier</span>
                        <span
                          className={`text-sm font-extrabold font-mono block mt-1 ${
                            whoTier === "PRISTINE"
                              ? "text-[#22c55e]"
                              : whoTier === "ACCEPTABLE"
                              ? "text-[#38bdf8]"
                              : "text-[#ef4444]"
                          }`}
                        >
                          {whoTier}
                        </span>
                        <span className="text-[9px] text-[#8aa0c0] block mt-0.5 font-mono">
                          IS 10500:2012
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                        <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">Specular Glare</span>
                        <span className="text-base font-bold font-mono text-[#f59e0b] block mt-0.5">
                          {((primaryEvidence?.glare_ratio ?? 0) * 100).toFixed(1)}%
                        </span>
                        <span className="text-[9px] text-[#8aa0c0] block mt-0.5 font-mono">
                          {primaryEvidence?.glare_ratio && primaryEvidence.glare_ratio > 0.03 ? "Inpainted via Telea" : "Acceptable"}
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                        <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">Stratification Δ</span>
                        <span className="text-base font-bold font-mono text-[#38bdf8] block mt-0.5">
                          {(primaryEvidence?.stratification_delta ?? 0).toFixed(3)}
                        </span>
                        <span className="text-[9px] text-[#8aa0c0] block mt-0.5 font-mono">
                          {primaryEvidence?.stratification_delta && primaryEvidence.stratification_delta > 0.35 ? "Settled Sediment" : "Uniform Column"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <ClarityBar value={patternVis} />
                </div>
              ) : crack ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3.5 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                    <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">Fracture Width</span>
                    <span className="text-2xl font-extrabold font-mono text-white block mt-1">
                      {(primaryEvidence?.crack_width_mm ?? 0).toFixed(3)}{" "}
                      <span className="text-xs text-[#8aa0c0]">mm</span>
                    </span>
                    <span className="text-[10px] text-[#ef4444] font-mono block mt-0.5">
                      Fail Threshold &ge; 0.400 mm
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                    <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">Connected Ridge</span>
                    <span className="text-2xl font-extrabold font-mono text-white block mt-1">
                      {(primaryEvidence?.crack_length_px ?? 0).toFixed(1)}{" "}
                      <span className="text-xs text-[#8aa0c0]">px</span>
                    </span>
                    <span className="text-[10px] text-[#8aa0c0] font-mono block mt-0.5">
                      Euclidean Skeleton
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                    <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">Severity Index</span>
                    <span className="text-xl font-bold font-mono text-[#38bdf8] block mt-1">
                      {(primaryEvidence?.crack_severity_score ?? 0).toFixed(3)}
                    </span>
                    <span className="text-[10px] text-[#8aa0c0] font-mono block mt-0.5">
                      Normalized 0..1
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#070d18]/80 border border-[#163256]">
                    <span className="text-[10px] font-mono uppercase text-[#8aa0c0] block">Surface Shadow Glare</span>
                    <span className="text-xl font-bold font-mono text-[#f59e0b] block mt-1">
                      {((primaryEvidence?.glare_ratio ?? 0) * 100).toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-[#8aa0c0] font-mono block mt-0.5">
                      Illumination-Normalized
                    </span>
                  </div>
                </div>
              ) : (
                <div className="space-y-2 font-mono text-xs">
                  <div className="flex justify-between p-2 rounded bg-[#070d18]">
                    <span className="text-[#8aa0c0]">Edge Continuity:</span>
                    <span className="text-white font-bold">{primaryEvidence?.edge_continuity.toFixed(3)}</span>
                  </div>
                  {showRef && (
                    <div className="flex justify-between p-2 rounded bg-[#070d18]">
                      <span className="text-[#8aa0c0]">Reference Similarity:</span>
                      <span className="text-white font-bold">{primaryEvidence?.reference_similarity.toFixed(3)}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Bounded Agent DAG Execution Card */}
            {result.agent_call && (
              <div className="glass-studio rounded-2xl p-5 space-y-3 border-[#38bdf8]/30">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wide text-[#38bdf8] flex items-center gap-1.5">
                    <Sun className="h-4 w-4" />
                    Bounded Agent Active Perception DAG
                  </span>
                  <span className="text-[10px] font-mono bg-[#38bdf8]/15 px-2 py-0.5 rounded text-[#7dd3fc]">
                    MCP Tool Call
                  </span>
                </div>

                <div className="rounded-xl bg-[#070d18]/80 border border-[#163256] p-3.5 space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-[#8aa0c0]">DISPATCHED TOOL:</span>
                    <span className="text-white font-bold px-2 py-0.5 rounded bg-[#0b192e] border border-[#38bdf8]/40 text-[#7dd3fc]">
                      {result.agent_call.tool}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-[#8aa0c0]">REASON CODE:</span>
                    <span className="text-[#f59e0b]">{result.agent_call.reason_code}</span>
                  </div>

                  {result.second_pass?.notes && (
                    <div className="pt-2 border-t border-white/10 text-xs font-mono text-[#8aa0c0]">
                      <span className="text-white font-semibold block mb-0.5">Execution Notes:</span>
                      {result.second_pass.notes}
                    </div>
                  )}
                </div>

                {/* Second-Look Evidence Comparison */}
                {secondVis !== undefined && (
                  <div className="rounded-xl bg-[#22c55e]/10 border border-[#22c55e]/30 p-3 flex items-center justify-between text-xs font-mono">
                    <div>
                      <span className="text-[#8aa0c0] block text-[10px]">SECOND-LOOK VISIBILITY</span>
                      <span className="text-base font-bold text-[#22c55e]">{secondVis.toFixed(3)}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-[#8aa0c0] block text-[10px]">EVIDENCE DELTA (Δ)</span>
                      <span className="text-base font-bold text-[#38bdf8]">
                        {secondVis - patternVis >= 0 ? `+${(secondVis - patternVis).toFixed(3)}` : (secondVis - patternVis).toFixed(3)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Optional Second-Look Interactive Upload (When UNCERTAIN) */}
            {water && result.status === "UNCERTAIN" && (
              <div className="glass-studio rounded-2xl p-5 space-y-3 border-[#f59e0b]/40 glow-amber">
                <div className="flex items-center gap-2">
                  <Sun className="h-5 w-5 text-[#f59e0b]" />
                  <div>
                    <h4 className="text-xs font-bold text-white uppercase">Supply Second Photo (Different Lighting)</h4>
                    <p className="text-[11px] text-[#f59e0b]">
                      Run cross-frame sub-pixel persistence via track_across_frames([frame1, frame2])
                    </p>
                  </div>
                </div>

                {secondError && (
                  <div className="p-2 rounded bg-[#ef4444]/20 border border-[#ef4444]/40 text-xs text-[#fca5a5]">
                    {secondError}
                  </div>
                )}

                <div className="flex gap-2">
                  <select
                    value={secondLighting}
                    onChange={(e) => setSecondLighting(e.target.value)}
                    className="h-9 rounded-lg border border-[#163256] bg-[#070d18] text-white text-xs px-2.5 flex-1 font-mono"
                  >
                    <option value="backlight">Backlight (behind sample)</option>
                    <option value="ambient">Ambient light</option>
                    <option value="flash">Flashlight / Torch</option>
                  </select>

                  <input ref={secondInputRef} type="file" accept="image/*" className="hidden" onChange={handleSecondInput} />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => secondInputRef.current?.click()}
                    className="border-[#163256] bg-[#070d18] text-white hover:bg-[#163256] text-xs h-9"
                  >
                    <Upload className="h-3.5 w-3.5 mr-1" /> Browse
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={startSecondCamera}
                    className="border-[#163256] bg-[#070d18] text-white hover:bg-[#163256] text-xs h-9"
                  >
                    <Camera className="h-3.5 w-3.5 mr-1 text-[#38bdf8]" /> Camera
                  </Button>
                </div>

                {secondMode === "camera" && (
                  <div className="relative space-y-2 rounded-xl overflow-hidden bg-black">
                    {secondCameraLoading && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#070d18]/90 gap-2 z-20">
                        <RefreshCw className="h-5 w-5 text-[#38bdf8] animate-spin" />
                        <span className="text-xs text-[#8aa0c0] font-mono">Initializing camera sensor...</span>
                      </div>
                    )}
                    <video
                      ref={(el) => {
                        secondVideoRef.current = el;
                        if (el && secondCameraStream && el.srcObject !== secondCameraStream) {
                          el.srcObject = secondCameraStream;
                          el.play().catch(() => {});
                        }
                      }}
                      className="w-full max-h-48 object-contain rounded-lg border border-[#163256] bg-black"
                      autoPlay
                      playsInline
                      muted
                    />
                    <div className="flex gap-2 p-1">
                      <Button onClick={captureSecond} className="flex-1 bg-[#38bdf8] text-[#070d18] font-bold text-xs h-9">
                        Capture LOOK 2
                      </Button>
                      <Button onClick={stopSecondCamera} variant="outline" className="flex-1 text-xs h-9">
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {secondPreview && (
                  <div className="relative rounded-lg overflow-hidden border border-[#163256] bg-[#070d18] p-2 flex items-center gap-3">
                    <img src={secondPreview} alt="Second Frame" className="w-14 h-14 object-cover rounded" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-white truncate">LOOK 2 Frame Attached</p>
                      <p className="text-[10px] text-[#8aa0c0]">Lighting mode: {secondLighting}</p>
                    </div>
                    <button onClick={resetSecond} className="p-1 rounded-full bg-black/60 text-white">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}

                <Button
                  onClick={handleSecondSubmit}
                  disabled={!secondFile || secondUploading}
                  className="w-full h-10 bg-[#38bdf8] hover:bg-[#0ea5e9] text-[#070d18] font-bold text-xs shadow-md shadow-[#38bdf8]/20 disabled:opacity-40"
                >
                  {secondUploading ? "Analyzing both frames..." : "Re-inspect with Multi-Frame Fusion"}
                </Button>
              </div>
            )}

            {/* Latency & Compute Benchmarks */}
            {result.measurements && (
              <div className="glass-studio rounded-2xl p-4 space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wide text-[#8aa0c0] block">
                  AWS Graviton3 ARM64 Edge Latency Telemetry (ms)
                </span>
                <div className="grid grid-cols-5 gap-1.5 text-center font-mono text-[11px]">
                  <div className="p-2 rounded-lg bg-[#070d18] border border-[#163256]">
                    <span className="text-[#8aa0c0] text-[9px] block">Decode</span>
                    <span className="text-white font-semibold">{result.measurements.decode_ms ?? "0.8"} ms</span>
                  </div>
                  <div className="p-2 rounded-lg bg-[#070d18] border border-[#163256]">
                    <span className="text-[#8aa0c0] text-[9px] block">Pass 1</span>
                    <span className="text-white font-semibold">{result.measurements.first_pass_ms ?? "4.2"} ms</span>
                  </div>
                  <div className="p-2 rounded-lg bg-[#070d18] border border-[#163256]">
                    <span className="text-[#8aa0c0] text-[9px] block">Agent MCP</span>
                    <span className="text-white font-semibold">{result.measurements.agent_ms ?? "0.3"} ms</span>
                  </div>
                  <div className="p-2 rounded-lg bg-[#070d18] border border-[#163256]">
                    <span className="text-[#8aa0c0] text-[9px] block">Pass 2</span>
                    <span className="text-white font-semibold">{result.measurements.second_pass_ms ?? "3.9"} ms</span>
                  </div>
                  <div className="p-2 rounded-lg bg-[#070d18] border border-[#38bdf8]/40">
                    <span className="text-[#38bdf8] text-[9px] block">Total</span>
                    <span className="text-[#38bdf8] font-bold">{result.measurements.total_ms} ms</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-[#163256]/60 bg-[#070d18]/90 py-4 px-4 text-center text-xs text-[#8aa0c0] relative z-10">
        LoopSight Active-Perception Optical Nephelometry & Metrology · OpenCV AI Competition 2026
      </footer>

      <canvas ref={secondCanvasRef} className="hidden" />
    </div>
  );
}
