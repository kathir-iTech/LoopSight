"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
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
  Check,
  AlertTriangle,
  XCircle,
  Clock,
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
} from "lucide-react";
import jsPDF from "jspdf";

function hasReference(result: InspectionResult): boolean {
  const gapMentionsRef = result.evidence_gap.some((g) => g.toLowerCase().includes("reference"));
  const anyNonOne = result.regions.some((r) => Math.abs(r.evidence.reference_similarity - 1.0) > 0.001);
  const secondHasRef =
    result.second_pass?.regions.some(
      (r) => r.reference_similarity !== undefined && typeof r.reference_similarity === "number" && Math.abs((r.reference_similarity as number) - 1.0) > 0.001
    ) ?? false;
  return gapMentionsRef || anyNonOne || secondHasRef;
}

function isWaterResult(result: InspectionResult): boolean {
  if (result.evidence_gap.some((g) => g.toLowerCase().includes("pattern visibility") || g.toLowerCase().includes("pattern not detected") || g.toLowerCase().includes("through water"))) return true;
  if (result.regions.some((r) => r.evidence.pattern_visibility !== undefined)) return true;
  if (result.second_pass?.regions.some((r) => (r as any).pattern_visibility !== undefined)) return true;
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
            cx={52} cy={52} r={38}
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
          <span className="text-[17px] font-bold tracking-tight" style={{ color: statusColor }}>{(pct * 100).toFixed(0)}%</span>
          <span className="text-[10px] tracking-widest uppercase" style={{ color: statusColor }}>{statusText}</span>
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
        <span className="text-[#ef4444]">Turbid</span>
        <span className="text-[#f59e0b]">Borderline</span>
        <span className="text-[#38bdf8]">Clear</span>
      </div>
      <div className="relative h-3 rounded-full overflow-hidden border border-white/10" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="absolute inset-0 rounded-full" style={{ background: "linear-gradient(90deg, #ef4444 0%, #f59e0b 38%, #38bdf8 72%, #0ea5e9 100%)", opacity: 0.95 }} />
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
        <span>0.20</span><span>0.55</span>
      </div>
    </div>
  );
}

function DecisionCard({ result }: { result: InspectionResult }) {
  const { decision, confidence_band, human_approval_required } = result.final_decision;
  const water = isWaterResult(result);
  const styles: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode; safety: string }> = {
    PASS: {
      bg: "bg-[#38bdf8]/10",
      border: "border-[#38bdf8]/30",
      text: "text-[#38bdf8]",
      icon: <Waves className="h-6 w-6 text-[#38bdf8]" />,
      safety: water
        ? "No visible turbidity detected — this does not confirm the water is safe. Invisible contaminants (arsenic, fluoride, nitrate) require a real water test."
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
        : "Defect confidently detected.",
    },
  };
  const s = styles[decision] || styles.REVIEW;
  return (
    <Card className={`${s.bg} ${s.border} border-2 overflow-hidden`}>
      <CardContent className="p-6">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${s.bg} border ${s.border}`}>{s.icon}</div>
          <div className="flex-1">
            <p className="text-xs uppercase tracking-widest text-[#8aa0c0]">Final Decision</p>
            <p className={`text-2xl font-bold tracking-tight ${s.text}`}>{decision}</p>
          </div>
          <Badge variant={decision === "PASS" ? "success" : decision === "FAIL" ? "destructive" : "warning"} className="text-sm px-3 py-1">
            {confidence_band} confidence
          </Badge>
        </div>
        <div className={`mt-4 rounded-xl border p-3 flex gap-2.5 ${decision === "PASS" ? "bg-[#0a1628]/60 border-[#38bdf8]/15" : "bg-[#ef4444]/5 border-[#ef4444]/15"}`}>
          <ShieldAlert className={`h-4 w-4 flex-shrink-0 mt-0.5 ${decision === "PASS" ? "text-[#38bdf8]" : "text-[#ef4444]"}`} />
          <p className={`text-xs leading-relaxed ${decision === "PASS" ? "text-[#8aa0c0]" : "text-[#fca5a5]"}`}>{s.safety}</p>
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm">
          <span className="text-[#8aa0c0]">Human approval required:</span>
          <span className={`font-medium ${human_approval_required ? "text-[#f59e0b]" : "text-[#38bdf8]"}`}>
            {human_approval_required ? "Yes — do not drink without treatment" : "No"}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function JobPage() {
  const params = useParams();
  const id = params.id as string;

  const [result, setResult] = useState<InspectionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollElapsed, setPollElapsed] = useState(0);
  // Phase 3 — second lighting capture state (for genuine track_across_frames)
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
            setError("Inspection is taking longer than expected. Please try again or refresh the page.");
            setPolling(false); setLoading(false);
            if (pollTimer) clearInterval(pollTimer);
            if (elapsedTimer) clearInterval(elapsedTimer);
            return;
          }
          return;
        }
        setResult(data); setPolling(false); setLoading(false);
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
        setError(msg); setLoading(false); setPolling(false);
        if (pollTimer) clearInterval(pollTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);
      }
    };
    fetchJob();
    pollTimer = setInterval(() => {
      if (polling || loading) fetchJob();
      else { if (result) { if (pollTimer) clearInterval(pollTimer); if (elapsedTimer) clearInterval(elapsedTimer); } else fetchJob(); }
    }, 1500);
    elapsedTimer = setInterval(() => setPollElapsed((prev) => prev + 0.1), 100);
    timeoutTimer = setTimeout(() => {
      if (!cancelled && (polling || loading) && !result) {
        setError("Inspection timed out after 30s. The backend may be unavailable — please try again.");
        setPolling(false); setLoading(false);
        if (pollTimer) clearInterval(pollTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);
      }
    }, 30000);
    return () => { cancelled = true; if (pollTimer) clearInterval(pollTimer); if (elapsedTimer) clearInterval(elapsedTimer); if (timeoutTimer) clearTimeout(timeoutTimer); };
  }, [id]);

  useEffect(() => {
    if (result || polling || !loading) return;
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
        if (!r.ok) throw new Error("Job not found");
        const data = await r.json();
        if ((data as any).status !== "processing") {
          setResult(data); setLoading(false);
          try { saveToHistory({ job_id: id, timestamp: new Date().toISOString(), decision: (data as InspectionResult).final_decision.decision, thumbnail_url: null }); } catch {}
        } else setPolling(true);
      } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to load"); setLoading(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [id, result, polling, loading]);

  const copyTrace = useCallback(async () => {
    if (!result) return;
    try { await navigator.clipboard.writeText(JSON.stringify(result, null, 2)); toast.success("Trace copied to clipboard"); } catch { toast.error("Failed to copy"); }
  }, [result]);
  const shareLink = useCallback(async () => {
    try { await navigator.clipboard.writeText(window.location.href); toast.success("Link copied to clipboard"); } catch { toast.error("Failed to copy link"); }
  }, []);
  const downloadReport = useCallback(() => {
    if (!result) return;
    try {
      const doc = new jsPDF();
      const now = new Date().toLocaleString();
      doc.setFontSize(18); doc.text("LoopSight — Water Inspection Report", 14, 20);
      doc.setFontSize(10); doc.setTextColor(100);
      doc.text(`Job ID: ${id}`, 14, 28); doc.text(`Generated: ${now}`, 14, 33); doc.text(`Status: ${result.status}`, 14, 38);
      doc.setTextColor(0); doc.setFontSize(12); doc.text("Perception — Pattern Visibility", 14, 48);
      doc.setFontSize(9);
      result.regions.forEach((r, i) => {
        const y = 54 + i * 22;
        const ev: any = r.evidence;
        const pv = ev.pattern_visibility !== undefined ? ` pattern_visibility=${ev.pattern_visibility.toFixed(3)} sharp=${(ev.pattern_sharpness ?? 0).toFixed(3)}${ev.pattern_found !== undefined ? ` found=${ev.pattern_found}` : ""}` : "";
        doc.text(`Region ${i+1} (${r.x},${r.y} ${r.w}x${r.h}): edge=${r.evidence.edge_continuity.toFixed(3)}${pv}  ref_sim=${r.evidence.reference_similarity.toFixed(3)}`, 14, y);
      });
      let yPos = 54 + result.regions.length * 22 + 6;
      if (result.evidence_gap.length) { doc.text(`Evidence gap: ${result.evidence_gap.join("; ")}`, 14, yPos); yPos+=8; }
      if (result.agent_call) { doc.text(`Agent: ${result.agent_call.tool} (${result.agent_call.reason_code})`, 14, yPos); yPos+=8; }
      if (result.second_pass) { doc.text("Second Pass (After second look):", 14, yPos); yPos+=6; result.second_pass.regions.forEach((r,i)=>{ doc.text(`  Region ${i+1}: ${JSON.stringify(r)}`, 14, yPos); yPos+=6; });}
      yPos+=4; doc.setFontSize(12); doc.text(`Final Decision: ${result.final_decision.decision} (${result.final_decision.confidence_band})`, 14, yPos); yPos+=7;
      doc.setFontSize(9); doc.text(`Human approval required: ${result.final_decision.human_approval_required ? "Yes" : "No"}`, 14, yPos); yPos+=8;
      doc.setFontSize(8); doc.setTextColor(130);
      doc.text("Safety: No visible turbidity does NOT confirm safe water — invisible contaminants require a real water test. Visible turbidity: do not drink without treatment.", 14, 275);
      doc.text("Generated by LoopSight — demo mode, not a certified inspection", 14, 285);
      doc.save(`loopsight-water-${id}.pdf`); toast.success("Report downloaded");
    } catch { toast.error("Failed to generate PDF"); }
  }, [result, id]);

  // Second lighting capture — genuine two-frame path (Phase 3)
  const handleSecondFileSelect = useCallback((file: File) => {
    setSecondFile(file);
    const url = URL.createObjectURL(file);
    setSecondPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return url; });
    setSecondError(null);
  }, []);
  const handleSecondInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (f) handleSecondFileSelect(f); e.target.value = "";
  }, [handleSecondFileSelect]);
  const startSecondCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      if (secondVideoRef.current) { secondVideoRef.current.srcObject = stream; secondVideoRef.current.play(); }
      setSecondMode("camera"); setSecondError(null);
    } catch { setSecondError("Camera access denied or unavailable."); }
  }, []);
  const captureSecond = useCallback(() => {
    if (!secondVideoRef.current || !secondCanvasRef.current) return;
    const v = secondVideoRef.current; const c = secondCanvasRef.current;
    c.width = v.videoWidth; c.height = v.videoHeight;
    const ctx = c.getContext("2d")!; ctx.drawImage(v, 0, 0);
    c.toBlob((blob) => { if (blob) handleSecondFileSelect(new File([blob], "capture2.jpg", { type: "image/jpeg" })); }, "image/jpeg", 0.9);
    (v.srcObject as MediaStream)?.getTracks().forEach((t) => t.stop());
    setSecondMode("idle");
  }, [handleSecondFileSelect]);
  const stopSecondCamera = useCallback(() => { (secondVideoRef.current?.srcObject as MediaStream)?.getTracks().forEach((t)=>t.stop()); setSecondMode("idle"); }, []);
  const resetSecond = useCallback(() => { if (secondPreview) URL.revokeObjectURL(secondPreview); setSecondPreview(null); setSecondFile(null); setSecondMode("idle"); setSecondError(null); }, [secondPreview]);
  const handleSecondSubmit = useCallback(async () => {
    if (!secondFile || !result) return;
    setSecondUploading(true); setSecondError(null);
    try {
      const form = new FormData();
      // Send original job id + second image (as 'image') + lighting2 — backend fetches cached first frame and calls track_across_frames([frame1, frame2]) for real
      form.append("original_job_id", id);
      form.append("image", secondFile);
      form.append("lighting2", secondLighting);
      const isWater = result.regions.some((r) => (r.evidence as any).pattern_visibility !== undefined);
      form.append("inspection_profile", isWater ? "water_turbidity_v1" : "fdm_print_surface_v1");
      const res = await fetch("/api/inspect", { method: "POST", body: form });
      if (!res.ok) throw new Error("Second look failed");
      const { job_id } = await res.json();
      toast.success("Second lighting submitted — analyzing...");
      window.location.href = `/job/${job_id}`;
    } catch (e: any) {
      setSecondError(e.message || "Failed to submit second photo.");
      toast.error("Failed to submit second photo.");
      setSecondUploading(false);
    }
  }, [secondFile, secondLighting, result, id]);

  if (loading || polling) {
    return (
      <div className="min-h-screen bg-[#0a1628] relative flex flex-col items-center justify-center p-4 overflow-hidden">
        <div className="ripple-bg" aria-hidden><div className="ripple-wave ripple-wave-1" /><div className="ripple-wave ripple-wave-2" /></div>
        <div className="w-full max-w-md space-y-6 text-center relative z-10">
          <div className="flex flex-col items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-[#38bdf8]/15 border border-[#38bdf8]/30 flex items-center justify-center">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}><RefreshCw className="h-7 w-7 text-[#38bdf8]" /></motion.div>
            </div>
            <div><p className="text-white font-medium">Checking water clarity...</p><p className="text-sm text-[#8aa0c0] mt-1">{polling ? `Analyzing pattern visibility · ${pollElapsed.toFixed(1)}s` : "Running OpenCV first pass"}</p></div>
          </div>
          <div className="w-full h-2 bg-[#0f2942] rounded-full overflow-hidden border border-[#1e3a5f]/50">
            <motion.div className="h-full rounded-full" style={{ background: "linear-gradient(90deg, #0ea5e9, #38bdf8, #7dd3fc)", width: "55%" }} initial={{ x: "-100%" }} animate={{ x: "100%" }} transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }} />
          </div>
          <div className="flex justify-center gap-1.5">
            <motion.span animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 0.8, repeat: Infinity, delay: 0 }} className="w-2 h-2 rounded-full bg-[#38bdf8]" />
            <motion.span animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 0.8, repeat: Infinity, delay: 0.2 }} className="w-2 h-2 rounded-full bg-[#38bdf8]" />
            <motion.span animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 0.8, repeat: Infinity, delay: 0.4 }} className="w-2 h-2 rounded-full bg-[#38bdf8]" />
          </div>
          <p className="text-xs text-[#5a7aa0]">Polling every 1.5s · timeout 30s</p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-[#0a1628] flex flex-col items-center justify-center gap-4 p-4">
        <div className="w-16 h-16 rounded-2xl bg-[#0f2942] border border-[#1e3a5f] flex items-center justify-center"><XCircle className="h-8 w-8 text-[#8aa0c0]" /></div>
        <p className="text-[#fca5a5] text-center max-w-md">{error || "Job not found"}</p>
        <Link href="/"><Button variant="outline">Back to water check</Button></Link>
      </div>
    );
  }

  const showRef = hasReference(result);
  const water = isWaterResult(result);
  const history = typeof window !== "undefined" ? loadHistory() : [];
  const todayCount = history.filter((h) => { const d = new Date(h.timestamp); const now = new Date(); return d.toDateString() === now.toDateString(); }).length;
  const inspectionIndex = history.findIndex((h) => h.job_id === id);
  const inspectionLabel = inspectionIndex >= 0 && todayCount > 0 ? `Inspection ${todayCount - inspectionIndex} of ${todayCount} today` : null;
  const statusVariant = result.status === "UNCERTAIN" ? "warning" : result.status === "CONFIDENT_PASS" ? "success" : "destructive";

  // Try to surface frame timestamps if present (Phase 3: second look with two lightings)
  const frameInfo: null | { seq: string; ts: string } = (() => {
    const any: any = result as any;
    if (any.frame_info) return any.frame_info;
    if (any.frames && Array.isArray(any.frames) && any.frames[0]?.timestamp) return { seq: any.frames.map((f:any)=>f.seq).join("→"), ts: any.frames.map((f:any)=>f.timestamp).join(" → ") };
    return null;
  })();

  return (
    <div className="min-h-screen bg-[#0a1628] relative">
      <div className="ripple-bg" aria-hidden><div className="ripple-wave ripple-wave-1" style={{ opacity: 0.025 }} /><div className="ripple-wave ripple-wave-2" style={{ opacity: 0.02 }} /></div>
      <header className="sticky top-0 z-10 backdrop-blur-xl bg-[#0a1628]/80 border-b border-[#1e3a5f]/60">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#0ea5e9] to-[#38bdf8] flex items-center justify-center"><Droplets className="h-4 w-4 text-white" /></div>
            <span className="font-semibold text-white hidden sm:inline">LoopSight</span>
            <span className="text-xs text-[#8aa0c0] hidden md:inline ml-1">{water ? "Water Trace" : "Evidence Trace"}</span>
          </Link>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs hidden sm:flex border-[#1e3a5f] text-[#8aa0c0]">{id}</Badge>
            <Link href="/"><Button variant="outline" size="sm">New check</Button></Link>
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-6 md:py-8 space-y-4 relative z-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-white flex items-center gap-2"><Waves className="h-5 w-5 text-[#38bdf8]" />{water ? "Water Clarity Trace" : "Evidence Trace"}</h1>
            {inspectionLabel && <p className="text-xs text-[#8aa0c0] mt-1">{inspectionLabel}</p>}
            {frameInfo && <p className="text-[11px] font-mono text-[#5a7aa0] mt-1">Frames: {frameInfo.seq} · {frameInfo.ts}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={copyTrace}><Copy className="h-3.5 w-3.5 mr-1.5" />Copy trace</Button>
            <Button variant="outline" size="sm" onClick={shareLink}><Share2 className="h-3.5 w-3.5 mr-1.5" />Share</Button>
            <Button variant="outline" size="sm" onClick={downloadReport}><Download className="h-3.5 w-3.5 mr-1.5" />PDF</Button>
          </div>
        </div>

        {water && (
          <div className="rounded-xl bg-[#38bdf8]/10 border border-[#38bdf8]/15 px-4 py-3 flex gap-2.5">
            <ShieldAlert className="h-4 w-4 text-[#38bdf8] flex-shrink-0 mt-0.5" />
            <p className="text-xs leading-relaxed text-[#8aa0c0]">Turbidity is <span className="text-[#e6f0ff] font-medium">not potability</span>. Clear-looking water can still carry arsenic, fluoride, or nitrate. This check flags <span className="text-[#38bdf8]">visibly cloudy water</span> — it is not a substitute for a real water test.</p>
          </div>
        )}

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0 }}>
          <Card className="border-[#1e3a5f]/50">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#38bdf8]/15 border border-[#38bdf8]/20 flex items-center justify-center">{water ? <Droplets className="h-3.5 w-3.5 text-[#38bdf8]" /> : <Eye className="h-3.5 w-3.5 text-[#38bdf8]" />}</span>
                  1. Perception
                  <span className="text-xs font-normal text-[#8aa0c0]">{water ? "Pattern through water" : "First look"}</span>
                </CardTitle>
                <Badge variant={statusVariant as any}>{result.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {result.evidence_gap.length > 0 && (
                <div className="rounded-xl bg-[#f59e0b]/10 border border-[#f59e0b]/20 p-3">
                  <p className="text-xs font-medium text-[#f59e0b] mb-1.5 flex items-center gap-1.5"><AlertTriangle className="h-3.5 w-3.5" />Evidence gap</p>
                  <ul className="list-disc list-inside text-sm text-[#fcd34d] space-y-0.5">
                    {result.evidence_gap.map((gap, i) => (<li key={i}>{gap}</li>))}
                  </ul>
                </div>
              )}
              {result.regions.map((region, i) => {
                const ev: any = region.evidence;
                const pv = ev.pattern_visibility;
                const waterRegion = pv !== undefined;
                return (
                  <div key={i} className="rounded-2xl bg-[#0a1628] border border-[#1e3a5f]/50 p-4">
                    <p className="text-xs text-[#5a7aa0] mb-3 font-mono">Region ({region.x}, {region.y}) × {region.w}×{region.h}{ev.pattern_found !== undefined ? ` · pattern ${ev.pattern_found ? "found" : "not found"}` : ""}</p>
                    {waterRegion ? (
                      <div className="space-y-4">
                        <div className="flex flex-wrap gap-6 justify-center py-2">
                          <ClarityGauge value={pv ?? 0} label="Pattern visibility" sublabel="clarity through water" />
                          <div className="flex flex-col gap-3 justify-center min-w-[180px]">
                            <div>
                              <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Sharpness</p>
                              <p className="font-mono font-semibold text-white text-base mt-1">{(ev.pattern_sharpness ?? 0).toFixed(3)}</p>
                              <div className="mt-1.5 h-1.5 bg-[#0f2942] rounded-full overflow-hidden border border-[#1e3a5f]/30"><div className="h-full rounded-full" style={{ width: `${Math.min(100, (ev.pattern_sharpness ?? 0) * 100)}%`, background: "#38bdf8" }} /></div>
                            </div>
                            <div>
                              <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Local contrast</p>
                              <p className="font-mono font-semibold text-white text-base mt-1">{(ev.local_contrast ?? ev.edge_continuity ?? 0).toFixed(3)}</p>
                              <div className="mt-1.5 h-1.5 bg-[#0f2942] rounded-full overflow-hidden border border-[#1e3a5f]/30"><div className="h-full rounded-full" style={{ width: `${Math.min(100, (ev.local_contrast ?? 0) * 100)}%`, background: "#7dd3fc" }} /></div>
                            </div>
                            {showRef && (
                              <div>
                                <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Ref. similarity</p>
                                <p className="font-mono font-semibold text-white text-base mt-1">{ev.reference_similarity.toFixed(3)}</p>
                              </div>
                            )}
                          </div>
                        </div>
                        <ClarityBar value={pv ?? 0} />
                        <p className="text-[11px] text-[#5a7aa0] text-center">Thresholds: ≤0.20 turbid · ≥0.55 clear · between = borderline (needs different lighting)</p>
                      </div>
                    ) : (
                      <div className={`grid gap-4 text-sm ${showRef ? "grid-cols-3" : "grid-cols-2"}`}>
                        <div>
                          <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Edge continuity</p>
                          <p className="font-mono font-semibold text-white text-base mt-1">{region.evidence.edge_continuity.toFixed(3)}</p>
                          <div className="mt-1.5 h-1 bg-[#0f2942] rounded-full overflow-hidden border border-[#1e3a5f]/30"><div className="h-full rounded-full" style={{ width: `${Math.min(100, region.evidence.edge_continuity * 100)}%`, background: "#38bdf8" }} /></div>
                        </div>
                        {showRef && (
                          <div>
                            <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Ref. similarity</p>
                            <p className="font-mono font-semibold text-white text-base mt-1">{region.evidence.reference_similarity.toFixed(3)}</p>
                            <div className="mt-1.5 h-1 bg-[#0f2942] rounded-full overflow-hidden border border-[#1e3a5f]/30"><div className="h-full rounded-full" style={{ width: `${Math.min(100, region.evidence.reference_similarity * 100)}%`, background: "#22c55e" }} /></div>
                          </div>
                        )}
                        <div>
                          <p className="text-[#8aa0c0] text-xs uppercase tracking-wide">Layer align. dev.</p>
                          <p className="font-mono font-semibold text-white text-base mt-1">{region.evidence.layer_alignment_deviation.toFixed(3)}</p>
                          <div className="mt-1.5 h-1 bg-[#0f2942] rounded-full overflow-hidden border border-[#1e3a5f]/30"><div className="h-full rounded-full" style={{ width: `${Math.min(100, region.evidence.layer_alignment_deviation * 100)}%`, background: "#f59e0b" }} /></div>
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
            <motion.div initial={{ opacity: 0, scaleY: 0 }} animate={{ opacity: 1, scaleY: 1 }} transition={{ duration: 0.3, delay: 0.2 }} className="flex flex-col items-center gap-1">
              <div className="w-px h-6 bg-gradient-to-b from-[#38bdf8]/50 to-[#38bdf8]/10" />
              <div className="w-6 h-6 rounded-full bg-[#38bdf8]/15 border border-[#38bdf8]/30 flex items-center justify-center"><ArrowDown className="h-3 w-3 text-[#7dd3fc]" /></div>
            </motion.div>
          </div>
        )}

        {result.agent_call && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
            <Card className="border-[#38bdf8]/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#38bdf8]/15 border border-[#38bdf8]/30 flex items-center justify-center"><Sun className="h-3.5 w-3.5 text-[#38bdf8]" /></span>
                  2. Agent Decision
                  <span className="text-xs font-normal text-[#8aa0c0]">{water ? "Lighting variation requested" : "Uncertainty → tool"}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-xl bg-[#38bdf8]/10 border border-[#38bdf8]/20 p-4">
                  <p className="text-xs uppercase tracking-widest text-[#38bdf8] mb-3">Decision node</p>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="inline-flex items-center px-3 py-1.5 rounded-xl bg-[#0a1628] border border-[#1e3a5f] font-mono text-sm text-[#e6f0ff]">{result.agent_call.tool}</span>
                    <span className="text-[#5a7aa0]">→</span>
                    <span className="text-sm text-[#8aa0c0]">reason: <span className="font-mono text-[#e6f0ff] bg-[#0f2942] px-2 py-1 rounded-lg border border-[#1e3a5f]">{result.agent_call.reason_code}</span></span>
                  </div>
                  <p className="text-xs text-[#5a7aa0] mt-3">{water ? "Whitelisted · for water, track_across_frames = different lighting (backlight vs ambient / flash)" : "Whitelisted tool · bounded to 1 step"}</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {result.agent_call && result.second_pass && (
          <div className="flex justify-center -my-1">
            <motion.div initial={{ opacity: 0, scaleY: 0 }} animate={{ opacity: 1, scaleY: 1 }} transition={{ duration: 0.3, delay: 0.4 }} className="flex flex-col items-center gap-1">
              <div className="w-px h-6 bg-gradient-to-b from-[#38bdf8]/30 to-[#22c55e]/20" />
              <div className="w-6 h-6 rounded-full bg-[#22c55e]/15 border border-[#22c55e]/20 flex items-center justify-center"><ArrowDown className="h-3 w-3 text-[#22c55e]" /></div>
            </motion.div>
          </div>
        )}

        {result.second_pass && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.4 }}>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#22c55e]/15 border border-[#22c55e]/20 flex items-center justify-center"><Eye className="h-3.5 w-3.5 text-[#22c55e]" /></span>
                  3. New Evidence
                  <span className="text-xs font-normal text-[#8aa0c0]">{water ? "After different lighting" : "After second look"}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.second_pass.regions.map((region, i) => {
                    const pv: any = (region as any).pattern_visibility;
                    const waterSec = pv !== undefined;
                    return (
                      <div key={i} className="rounded-xl bg-[#0a1628] border border-[#1e3a5f]/50 p-4">
                        <p className="text-xs text-[#5a7aa0] mb-3">Second-pass region {i + 1}{waterSec ? " · re-measured after lighting variation" : ""}</p>
                        {waterSec ? (
                          <div className="space-y-3">
                            <div className="flex flex-wrap gap-4 items-center">
                              <ClarityGauge value={(region as any).pattern_visibility ?? region.edge_continuity} label="Second visibility" />
                              <div className="text-sm space-y-1.5">
                                {Object.entries(region).map(([key, val]) => {
                                  if (key === "pattern_visibility" && waterSec) return null;
                                  if (typeof val === "number" && val < 0) return null;
                                  if (key === "reference_similarity" && !showRef) return null;
                                  if (key === "pattern_found") return null;
                                  return <div key={key} className="flex gap-2"><span className="text-[#8aa0c0] text-xs uppercase">{key.replace(/_/g, " ")}</span><span className="font-mono text-white text-xs">{typeof val === "number" ? (val as number).toFixed(3) : String(val)}</span></div>;
                                })}
                              </div>
                            </div>
                            <ClarityBar value={(region as any).pattern_visibility ?? region.edge_continuity} />
                          </div>
                        ) : (
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {Object.entries(region).map(([key, val]) => {
                              if (key === "reference_similarity" && !showRef) return null;
                              if (typeof val === "number" && val < 0) return null;
                              return <div key={key}><p className="text-[#8aa0c0] text-xs uppercase tracking-wide">{key.replace(/_/g, " ")}</p><p className="font-mono font-semibold text-white mt-1">{typeof val === "number" ? (val as number).toFixed(3) : String(val)}</p></div>;
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {result.second_pass && (
          <div className="flex justify-center -my-1">
            <motion.div initial={{ opacity: 0, scaleY: 0 }} animate={{ opacity: 1, scaleY: 1 }} transition={{ duration: 0.3, delay: 0.6 }} className="flex flex-col items-center gap-1"><div className="w-px h-6 bg-gradient-to-b from-[#22c55e]/20 to-transparent" /></motion.div>
          </div>
        )}

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: result.second_pass ? 0.6 : result.agent_call ? 0.4 : 0.2 }}>
          <DecisionCard result={result} />
        </motion.div>

        {/* Phase 3 — second lighting prompt: genuine track_across_frames when borderline */}
        {water && result.status === "UNCERTAIN" && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.65 }}>
            <Card className="border-[#38bdf8]/30 bg-[#0f2942]/60">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#f59e0b]/15 border border-[#f59e0b]/20 flex items-center justify-center"><Sun className="h-3.5 w-3.5 text-[#f59e0b]" /></span>
                  Take a second photo — different lighting
                  <span className="text-xs font-normal text-[#8aa0c0]">Resolves borderline visibility</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-xl bg-[#38bdf8]/10 border border-[#38bdf8]/15 p-3 flex gap-2.5">
                  <Waves className="h-4 w-4 text-[#38bdf8] flex-shrink-0 mt-0.5" />
                  <p className="text-xs leading-relaxed text-[#8aa0c0]">First look was borderline. A second photo under <span className="text-[#e6f0ff] font-medium">backlight, ambient, or phone flash</span> lets the agent compare pattern clarity across lightings — the real Secchi technique. This calls <span className="font-mono text-[#38bdf8]">track_across_frames</span> for real, not a simulated crop.</p>
                </div>
                {secondError && (
                  <div className="rounded-xl bg-[#ef4444]/10 border border-[#ef4444]/20 p-3 text-xs text-[#fca5a5]">{secondError}</div>
                )}
                <div className="space-y-3">
                  <div className="flex gap-2">
                    <select value={secondLighting} onChange={(e) => setSecondLighting(e.target.value)} className="h-10 rounded-xl border border-[#1e3a5f] bg-[#0a1628] text-[#e6f0ff] text-sm px-3 flex-1">
                      <option value="backlight">Backlight (behind glass)</option>
                      <option value="ambient">Ambient light</option>
                      <option value="flash">Phone flash</option>
                    </select>
                    <Button variant="outline" size="sm" onClick={() => secondInputRef.current?.click()} className="h-10">
                      <Upload className="h-4 w-4 mr-1.5" />Upload
                    </Button>
                    <Button variant="outline" size="sm" onClick={startSecondCamera} className="h-10">
                      <Camera className="h-4 w-4 mr-1.5" />Camera
                    </Button>
                  </div>
                  <input ref={secondInputRef} type="file" accept="image/*" className="hidden" onChange={handleSecondInput} />
                  {secondMode === "camera" && (
                    <div className="space-y-2">
                      <div className="rounded-xl overflow-hidden border border-[#1e3a5f] bg-black"><video ref={secondVideoRef} className="w-full max-h-64 object-contain" autoPlay playsInline muted /></div>
                      <div className="flex gap-2">
                        <Button onClick={captureSecond} className="flex-1 bg-[#38bdf8] hover:bg-[#0ea5e9] text-[#0a1628] font-semibold">Capture second</Button>
                        <Button onClick={stopSecondCamera} variant="outline" className="flex-1">Cancel</Button>
                      </div>
                    </div>
                  )}
                  {secondPreview && (
                    <div className="relative rounded-xl overflow-hidden border border-[#1e3a5f]/60 bg-[#0a1628]">
                      <img src={secondPreview} alt="Second lighting" className="w-full max-h-64 object-contain mx-auto" />
                      <button onClick={resetSecond} className="absolute top-2 right-2 rounded-full bg-black/60 backdrop-blur p-2 text-white hover:bg-black/80"><X className="h-4 w-4" /></button>
                    </div>
                  )}
                  <Button onClick={handleSecondSubmit} disabled={!secondFile || secondUploading} className="w-full h-11 bg-[#38bdf8] hover:bg-[#0ea5e9] text-[#0a1628] font-semibold shadow-lg shadow-[#38bdf8]/20 disabled:opacity-40">
                    {secondUploading ? (
                      <span className="flex items-center gap-2">Analyzing second lighting...<span className="flex gap-1 ml-1"><motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 0.9, repeat: Infinity, delay: 0 }} className="w-1 h-1 rounded-full bg-[#0a1628] inline-block" /><motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 0.9, repeat: Infinity, delay: 0.2 }} className="w-1 h-1 rounded-full bg-[#0a1628] inline-block" /><motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 0.9, repeat: Infinity, delay: 0.4 }} className="w-1 h-1 rounded-full bg-[#0a1628] inline-block" /></span></span>
                    ) : (
                      <>Submit second lighting → re-inspect with both frames</>
                    )}
                  </Button>
                  <p className="text-[11px] text-[#5a7aa0] text-center">Sends <span className="font-mono text-[#8aa0c0]">original_job_id={id}</span> + your second image to <span className="font-mono text-[#38bdf8]">track_across_frames([frame1, frame2])</span>. Look for <span className="text-[#8aa0c0]">LOOK 1 → LOOK 2</span> timestamps in the next trace.</p>
                </div>
                <canvas ref={secondCanvasRef} className="hidden" />
              </CardContent>
            </Card>
          </motion.div>
        )}

        {result.measurements && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.7 }}>
            <Card className="bg-[#0a1628]/50 border-[#1e3a5f]/40">
              <CardHeader className="pb-3"><CardTitle className="text-sm flex items-center gap-2 text-[#8aa0c0]"><Clock className="h-4 w-4" />Timings</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                  <div className="rounded-xl bg-[#0f2942] border border-[#1e3a5f] p-3"><p className="text-xs text-[#8aa0c0]">Decode</p><p className="font-mono font-medium text-white mt-1">{result.measurements.decode_ms} ms</p></div>
                  <div className="rounded-xl bg-[#0f2942] border border-[#1e3a5f] p-3"><p className="text-xs text-[#8aa0c0]">First pass</p><p className="font-mono font-medium text-white mt-1">{result.measurements.first_pass_ms} ms</p></div>
                  <div className="rounded-xl bg-[#0f2942] border border-[#1e3a5f] p-3"><p className="text-xs text-[#8aa0c0]">Agent</p><p className="font-mono font-medium text-white mt-1">{result.measurements.agent_ms ?? "—"} {result.measurements.agent_ms != null ? "ms" : ""}</p></div>
                  <div className="rounded-xl bg-[#0f2942] border border-[#1e3a5f] p-3"><p className="text-xs text-[#8aa0c0]">Second pass</p><p className="font-mono font-medium text-white mt-1">{result.measurements.second_pass_ms ?? "—"} {result.measurements.second_pass_ms != null ? "ms" : ""}</p></div>
                  <div className="rounded-xl bg-[#38bdf8]/10 border border-[#38bdf8]/20 p-3"><p className="text-xs text-[#38bdf8]">Total</p><p className="font-mono font-semibold text-white mt-1">{result.measurements.total_ms} ms</p></div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        <details className="rounded-xl border border-[#1e3a5f]/60 bg-[#0f2942]/40 overflow-hidden">
          <summary className="px-4 py-3 text-sm font-medium text-[#8aa0c0] cursor-pointer hover:text-white transition-colors select-none">Raw trace JSON</summary>
          <pre className="px-4 pb-4 text-xs font-mono text-[#8aa0c0] overflow-x-auto whitespace-pre-wrap break-all max-h-96 overflow-y-auto">{JSON.stringify(result, null, 2)}</pre>
        </details>

        <div className="text-center pt-2">
          <Link href="/" className="text-sm text-[#38bdf8] hover:text-[#7dd3fc] transition-colors">← Back to water check</Link>
        </div>
      </div>
    </div>
  );
}
