"use client";

import { useEffect, useState, useCallback } from "react";
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
  ScanSearch,
  Cpu,
  Eye,
} from "lucide-react";
import jsPDF from "jspdf";

// Helper to detect if reference was actually provided (hide fake 1.0)
function hasReference(result: InspectionResult): boolean {
  // If any region has reference_similarity meaningfully != 1.0, we had a reference
  // Also if evidence_gap mentions reference, we attempted comparison
  const gapMentionsRef = result.evidence_gap.some((g) => g.toLowerCase().includes("reference"));
  const anyNonOne = result.regions.some((r) => Math.abs(r.evidence.reference_similarity - 1.0) > 0.001);
  const secondHasRef =
    result.second_pass?.regions.some((r) => r.reference_similarity !== undefined && typeof r.reference_similarity === "number" && Math.abs((r.reference_similarity as number) - 1.0) > 0.001) ?? false;
  return gapMentionsRef || anyNonOne || secondHasRef;
}

function DecisionCard({ result }: { result: InspectionResult }) {
  const { decision, confidence_band, human_approval_required } = result.final_decision;

  const styles: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    PASS: {
      bg: "bg-[#22c55e]/10",
      border: "border-[#22c55e]/30",
      text: "text-[#22c55e]",
      icon: <Check className="h-6 w-6 text-[#22c55e]" />,
    },
    REVIEW: {
      bg: "bg-[#f59e0b]/10",
      border: "border-[#f59e0b]/30",
      text: "text-[#f59e0b]",
      icon: <AlertTriangle className="h-6 w-6 text-[#f59e0b]" />,
    },
    FAIL: {
      bg: "bg-[#ef4444]/10",
      border: "border-[#ef4444]/30",
      text: "text-[#ef4444]",
      icon: <XCircle className="h-6 w-6 text-[#ef4444]" />,
    },
  };
  const s = styles[decision] || styles.REVIEW;

  return (
    <Card className={`${s.bg} ${s.border} border-2`}>
      <CardContent className="p-6">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${s.bg} border ${s.border}`}>{s.icon}</div>
          <div className="flex-1">
            <p className="text-xs uppercase tracking-widest text-[#9ca3af]">Final Decision</p>
            <p className={`text-2xl font-bold tracking-tight ${s.text}`}>{decision}</p>
          </div>
          <Badge variant={decision === "PASS" ? "success" : decision === "FAIL" ? "destructive" : "warning"} className="text-sm px-3 py-1">
            {confidence_band} confidence
          </Badge>
        </div>
        <div className="mt-4 flex items-center gap-2 text-sm">
          <span className="text-[#9ca3af]">Human approval required:</span>
          <span className={`font-medium ${human_approval_required ? "text-[#f59e0b]" : "text-[#22c55e]"}`}>
            {human_approval_required ? "Yes — review queue" : "No"}
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

  // Fetch with polling if status === "processing"
  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let elapsedTimer: ReturnType<typeof setInterval> | null = null;
    let timeoutTimer: ReturnType<typeof setTimeout> | null = null;
    let attempts = 0;
    const maxAttempts = 20; // 20 * 1.5s = 30s

    const fetchJob = async () => {
      try {
        const r = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
        if (!r.ok) throw new Error("Job not found");
        const data = await r.json();
        if (cancelled) return;

        // Check if status is "processing" (string) — Phase 2 support
        // Our types have "CONFIDENT_PASS" etc as status, but if backend returns status:"processing", treat as polling
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const status = (data as any).status;
        if (status === "processing") {
          setPolling(true);
          attempts += 1;
          if (attempts >= maxAttempts) {
            setError("Inspection is taking longer than expected. Please try again or refresh the page.");
            setPolling(false);
            setLoading(false);
            if (pollTimer) clearInterval(pollTimer);
            if (elapsedTimer) clearInterval(elapsedTimer);
            return;
          }
          // continue polling — don't set result yet
          return;
        }

        setResult(data);
        setPolling(false);
        setLoading(false);
        if (pollTimer) clearInterval(pollTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);
        if (timeoutTimer) clearTimeout(timeoutTimer);

        // Save to history (Phase 4)
        try {
          const decision = (data as InspectionResult).final_decision?.decision || "UNKNOWN";
          saveToHistory({
            job_id: id,
            timestamp: new Date().toISOString(),
            decision,
            thumbnail_url: null,
          });
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

    // Initial fetch
    fetchJob();

    // If first fetch indicates polling, start interval
    // We'll set up polling after first fetch completes if status was processing
    // Simpler: always set up polling interval that checks; it will no-op if not processing
    pollTimer = setInterval(() => {
      // Only poll if we are in polling state or still loading
      if (polling || loading) {
        fetchJob();
      } else {
        // Check if we already have result — stop
        if (result) {
          if (pollTimer) clearInterval(pollTimer);
          if (elapsedTimer) clearInterval(elapsedTimer);
        } else {
          // Still no result, keep polling until attempts exceeded
          fetchJob();
        }
      }
    }, 1500);

    elapsedTimer = setInterval(() => {
      setPollElapsed((prev) => prev + 0.1);
    }, 100);

    timeoutTimer = setTimeout(() => {
      if (!cancelled && (polling || loading) && !result) {
        setError("Inspection timed out after 30s. The backend may be unavailable — please try again.");
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Also do simple fetch once if not polling (fallback for non-processing backends)
  useEffect(() => {
    if (result || polling || !loading) return;
    // If loading is true but polling not yet set, ensure we fetch once more after 200ms
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
        if (!r.ok) throw new Error("Job not found");
        const data = await r.json();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ((data as any).status !== "processing") {
          setResult(data);
          setLoading(false);
          try {
            saveToHistory({
              job_id: id,
              timestamp: new Date().toISOString(),
              decision: (data as InspectionResult).final_decision.decision,
              thumbnail_url: null,
            });
          } catch {}
        } else {
          setPolling(true);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load");
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [id, result, polling, loading]);

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
      doc.setFontSize(18);
      doc.text("LoopSight — Inspection Report", 14, 20);
      doc.setFontSize(10);
      doc.setTextColor(100);
      doc.text(`Job ID: ${id}`, 14, 28);
      doc.text(`Generated: ${now}`, 14, 33);
      doc.text(`Status: ${result.status}`, 14, 38);
      doc.setTextColor(0);
      doc.setFontSize(12);
      doc.text("Perception — First Pass", 14, 48);
      doc.setFontSize(9);
      result.regions.forEach((r, i) => {
        const y = 54 + i * 18;
        doc.text(
          `Region ${i + 1} (${r.x},${r.y} ${r.w}x${r.h}): edge_continuity=${r.evidence.edge_continuity.toFixed(3)}  reference_similarity=${r.evidence.reference_similarity.toFixed(3)}  layer_alignment_deviation=${r.evidence.layer_alignment_deviation.toFixed(3)}`,
          14,
          y
        );
      });
      let yPos = 54 + result.regions.length * 18 + 6;
      if (result.evidence_gap.length) {
        doc.text(`Evidence gap: ${result.evidence_gap.join("; ")}`, 14, yPos);
        yPos += 8;
      }
      if (result.agent_call) {
        doc.text(`Agent: ${result.agent_call.tool} (${result.agent_call.reason_code})`, 14, yPos);
        yPos += 8;
      }
      if (result.second_pass) {
        doc.text("Second Pass (After second look):", 14, yPos);
        yPos += 6;
        result.second_pass.regions.forEach((r, i) => {
          doc.text(`  Region ${i + 1}: ${JSON.stringify(r)}`, 14, yPos);
          yPos += 6;
        });
      }
      yPos += 4;
      doc.setFontSize(12);
      doc.text(`Final Decision: ${result.final_decision.decision} (${result.final_decision.confidence_band})`, 14, yPos);
      yPos += 7;
      doc.setFontSize(9);
      doc.text(`Human approval required: ${result.final_decision.human_approval_required ? "Yes" : "No"}`, 14, yPos);
      yPos += 8;
      if (result.measurements) {
        doc.text(
          `Timings (ms): decode ${result.measurements.decode_ms} · first_pass ${result.measurements.first_pass_ms} · agent ${result.measurements.agent_ms ?? "-"} · second_pass ${result.measurements.second_pass_ms ?? "-"} · total ${result.measurements.total_ms}`,
          14,
          yPos
        );
        yPos += 8;
      }
      doc.setFontSize(8);
      doc.setTextColor(130);
      doc.text("Generated by LoopSight — demo mode, not a certified inspection", 14, 285);
      doc.save(`loopsight-${id}.pdf`);
      toast.success("Report downloaded");
    } catch {
      toast.error("Failed to generate PDF");
    }
  }, [result, id]);

  if (loading || polling) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] bg-gradient-loopsight flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-[#6366f1]/15 border border-[#6366f1]/30 flex items-center justify-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
              >
                <RefreshCw className="h-7 w-7 text-[#6366f1]" />
              </motion.div>
            </div>
            <div>
              <p className="text-white font-medium">Inspecting your print...</p>
              <p className="text-sm text-[#9ca3af] mt-1">
                {polling ? `Live analysis · ${pollElapsed.toFixed(1)}s elapsed` : "Running OpenCV first pass"}
              </p>
            </div>
          </div>
          <div className="w-full h-2 bg-[#1e1e2e] rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-[#6366f1] to-[#818cf8] rounded-full"
              initial={{ x: "-100%" }}
              animate={{ x: "100%" }}
              transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
              style={{ width: "55%" }}
            />
          </div>
          <div className="flex justify-center gap-1.5">
            <motion.span animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 0.8, repeat: Infinity, delay: 0 }} className="w-2 h-2 rounded-full bg-[#6366f1]" />
            <motion.span animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 0.8, repeat: Infinity, delay: 0.2 }} className="w-2 h-2 rounded-full bg-[#6366f1]" />
            <motion.span animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }} transition={{ duration: 0.8, repeat: Infinity, delay: 0.4 }} className="w-2 h-2 rounded-full bg-[#6366f1]" />
          </div>
          <p className="text-xs text-[#6b7280]">Polling every 1.5s · timeout 30s</p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] bg-gradient-loopsight flex flex-col items-center justify-center gap-4 p-4">
        <div className="w-16 h-16 rounded-2xl bg-[#1e1e2e] border border-[#1e1e2e] flex items-center justify-center">
          <XCircle className="h-8 w-8 text-[#9ca3af]" />
        </div>
        <p className="text-[#fca5a5] text-center max-w-md">{error || "Job not found"}</p>
        <Link href="/">
          <Button variant="outline">Back to inspection</Button>
        </Link>
      </div>
    );
  }

  const showRef = hasReference(result);
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

  return (
    <div className="min-h-screen bg-[#0a0a0f] bg-gradient-loopsight">
      {/* Header */}
      <header className="sticky top-0 z-10 backdrop-blur-xl bg-[#0a0a0f]/80 border-b border-[#1e1e2e]">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#6366f1] flex items-center justify-center">
              <ScanSearch className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-white hidden sm:inline">LoopSight</span>
            <span className="text-xs text-[#9ca3af] hidden md:inline ml-1">Evidence Trace</span>
          </Link>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs hidden sm:flex">
              {id}
            </Badge>
            <Link href="/">
              <Button variant="outline" size="sm">
                New inspection
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-6 md:py-8 space-y-4">
        {/* Top bar actions + inspection counter */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-white">Evidence Trace</h1>
            {inspectionLabel && <p className="text-xs text-[#9ca3af] mt-1">{inspectionLabel}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={copyTrace}>
              <Copy className="h-3.5 w-3.5 mr-1.5" />
              Copy trace as JSON
            </Button>
            <Button variant="outline" size="sm" onClick={shareLink}>
              <Share2 className="h-3.5 w-3.5 mr-1.5" />
              Share link
            </Button>
            <Button variant="outline" size="sm" onClick={downloadReport}>
              <Download className="h-3.5 w-3.5 mr-1.5" />
              Download report
            </Button>
          </div>
        </div>

        {/* Section 1: Perception */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0 }}
        >
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#6366f1]/15 border border-[#6366f1]/20 flex items-center justify-center">
                    <Eye className="h-3.5 w-3.5 text-[#818cf8]" />
                  </span>
                  1. Perception
                  <span className="text-xs font-normal text-[#9ca3af]">First look</span>
                </CardTitle>
                <Badge variant={statusVariant as "success" | "warning" | "destructive"}>{result.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {result.evidence_gap.length > 0 && (
                <div className="rounded-lg bg-[#f59e0b]/10 border border-[#f59e0b]/20 p-3">
                  <p className="text-xs font-medium text-[#f59e0b] mb-1.5 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Evidence gap
                  </p>
                  <ul className="list-disc list-inside text-sm text-[#fcd34d] space-y-0.5">
                    {result.evidence_gap.map((gap, i) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.regions.map((region, i) => (
                <div key={i} className="rounded-xl bg-[#0a0a0f] border border-[#1e1e2e] p-4">
                  <p className="text-xs text-[#6b7280] mb-3 font-mono">
                    Region ({region.x}, {region.y}) × {region.w}×{region.h}
                  </p>
                  <div className={`grid gap-4 text-sm ${showRef ? "grid-cols-3" : "grid-cols-2"}`}>
                    <div>
                      <p className="text-[#9ca3af] text-xs uppercase tracking-wide">Edge continuity</p>
                      <p className="font-mono font-semibold text-white text-base mt-1">{region.evidence.edge_continuity.toFixed(3)}</p>
                      <div className="mt-1.5 h-1 bg-[#1e1e2e] rounded-full overflow-hidden">
                        <div className="h-full bg-[#6366f1] rounded-full" style={{ width: `${Math.min(100, region.evidence.edge_continuity * 100)}%` }} />
                      </div>
                    </div>
                    {showRef && (
                      <div>
                        <p className="text-[#9ca3af] text-xs uppercase tracking-wide">Ref. similarity</p>
                        <p className="font-mono font-semibold text-white text-base mt-1">{region.evidence.reference_similarity.toFixed(3)}</p>
                        <div className="mt-1.5 h-1 bg-[#1e1e2e] rounded-full overflow-hidden">
                          <div className="h-full bg-[#22c55e] rounded-full" style={{ width: `${Math.min(100, region.evidence.reference_similarity * 100)}%` }} />
                        </div>
                      </div>
                    )}
                    <div>
                      <p className="text-[#9ca3af] text-xs uppercase tracking-wide">Layer align. dev.</p>
                      <p className="font-mono font-semibold text-white text-base mt-1">{region.evidence.layer_alignment_deviation.toFixed(3)}</p>
                      <div className="mt-1.5 h-1 bg-[#1e1e2e] rounded-full overflow-hidden">
                        <div className="h-full bg-[#f59e0b] rounded-full" style={{ width: `${Math.min(100, region.evidence.layer_alignment_deviation * 100)}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        {/* Connector: Perception -> Agent */}
        {result.agent_call && (
          <div className="flex justify-center -my-1">
            <motion.div
              initial={{ opacity: 0, scaleY: 0 }}
              animate={{ opacity: 1, scaleY: 1 }}
              transition={{ duration: 0.3, delay: 0.2 }}
              className="flex flex-col items-center gap-1"
            >
              <div className="w-px h-6 bg-gradient-to-b from-[#6366f1]/50 to-[#6366f1]/20" />
              <div className="w-6 h-6 rounded-full bg-[#6366f1]/15 border border-[#6366f1]/30 flex items-center justify-center">
                <ArrowDown className="h-3 w-3 text-[#818cf8]" />
              </div>
            </motion.div>
          </div>
        )}

        {/* Section 2: Agent Decision */}
        {result.agent_call && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Card className="border-[#6366f1]/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#6366f1]/15 border border-[#6366f1]/30 flex items-center justify-center">
                    <Cpu className="h-3.5 w-3.5 text-[#818cf8]" />
                  </span>
                  2. Agent Decision
                  <span className="text-xs font-normal text-[#9ca3af]">Uncertainty → tool selection</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-xl bg-[#6366f1]/10 border border-[#6366f1]/20 p-4">
                  <p className="text-xs uppercase tracking-widest text-[#818cf8] mb-3">Decision node</p>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="inline-flex items-center px-3 py-1.5 rounded-lg bg-[#0a0a0f] border border-[#1e1e2e] font-mono text-sm text-[#ededed]">
                      {result.agent_call.tool}
                    </span>
                    <span className="text-[#6b7280]">→</span>
                    <span className="text-sm text-[#9ca3af]">
                      reason: <span className="font-mono text-[#ededed] bg-[#1e1e2e] px-2 py-1 rounded">{result.agent_call.reason_code}</span>
                    </span>
                  </div>
                  <p className="text-xs text-[#6b7280] mt-3">Whitelisted tool · bounded to 1 step · deterministic validation</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {result.agent_call && result.second_pass && (
          <div className="flex justify-center -my-1">
            <motion.div
              initial={{ opacity: 0, scaleY: 0 }}
              animate={{ opacity: 1, scaleY: 1 }}
              transition={{ duration: 0.3, delay: 0.4 }}
              className="flex flex-col items-center gap-1"
            >
              <div className="w-px h-6 bg-gradient-to-b from-[#6366f1]/30 to-[#22c55e]/20" />
              <div className="w-6 h-6 rounded-full bg-[#22c55e]/15 border border-[#22c55e]/20 flex items-center justify-center">
                <ArrowDown className="h-3 w-3 text-[#22c55e]" />
              </div>
            </motion.div>
          </div>
        )}

        {/* Section 3: New Evidence */}
        {result.second_pass && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.4 }}
          >
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-[#22c55e]/15 border border-[#22c55e]/20 flex items-center justify-center">
                    <ScanSearch className="h-3.5 w-3.5 text-[#22c55e]" />
                  </span>
                  3. New Evidence
                  <span className="text-xs font-normal text-[#9ca3af]">After second look</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.second_pass.regions.map((region, i) => (
                    <div key={i} className="rounded-xl bg-[#0a0a0f] border border-[#1e1e2e] p-4">
                      <p className="text-xs text-[#6b7280] mb-3">Second-pass region {i + 1}</p>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {Object.entries(region).map(([key, val]) => {
                          // Hide reference_similarity if no reference (fake 1.0 filtered)
                          if (key === "reference_similarity" && !showRef) return null;
                          // Hide sentinel -1 values (not measured)
                          if (typeof val === "number" && val < 0) return null;
                          return (
                            <div key={key}>
                              <p className="text-[#9ca3af] text-xs uppercase tracking-wide">{key.replace(/_/g, " ")}</p>
                              <p className="font-mono font-semibold text-white mt-1">{typeof val === "number" ? val.toFixed(3) : String(val)}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {result.second_pass && (
          <div className="flex justify-center -my-1">
            <motion.div
              initial={{ opacity: 0, scaleY: 0 }}
              animate={{ opacity: 1, scaleY: 1 }}
              transition={{ duration: 0.3, delay: 0.6 }}
              className="flex flex-col items-center gap-1"
            >
              <div className="w-px h-6 bg-gradient-to-b from-[#22c55e]/20 to-transparent" />
            </motion.div>
          </div>
        )}

        {/* Section 4: Final Decision */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: result.second_pass ? 0.6 : result.agent_call ? 0.4 : 0.2 }}
        >
          <DecisionCard result={result} />
        </motion.div>

        {/* Measurements timing */}
        {result.measurements && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.7 }}
          >
            <Card className="bg-[#0a0a0f]/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2 text-[#9ca3af]">
                  <Clock className="h-4 w-4" />
                  Timings
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                  <div className="rounded-lg bg-[#12121a] border border-[#1e1e2e] p-3">
                    <p className="text-xs text-[#9ca3af]">Decode</p>
                    <p className="font-mono font-medium text-white mt-1">{result.measurements.decode_ms} ms</p>
                  </div>
                  <div className="rounded-lg bg-[#12121a] border border-[#1e1e2e] p-3">
                    <p className="text-xs text-[#9ca3af]">First pass</p>
                    <p className="font-mono font-medium text-white mt-1">{result.measurements.first_pass_ms} ms</p>
                  </div>
                  <div className="rounded-lg bg-[#12121a] border border-[#1e1e2e] p-3">
                    <p className="text-xs text-[#9ca3af]">Agent</p>
                    <p className="font-mono font-medium text-white mt-1">{result.measurements.agent_ms ?? "—"} {result.measurements.agent_ms != null ? "ms" : ""}</p>
                  </div>
                  <div className="rounded-lg bg-[#12121a] border border-[#1e1e2e] p-3">
                    <p className="text-xs text-[#9ca3af]">Second pass</p>
                    <p className="font-mono font-medium text-white mt-1">{result.measurements.second_pass_ms ?? "—"} {result.measurements.second_pass_ms != null ? "ms" : ""}</p>
                  </div>
                  <div className="rounded-lg bg-[#6366f1]/10 border border-[#6366f1]/20 p-3">
                    <p className="text-xs text-[#818cf8]">Total</p>
                    <p className="font-mono font-semibold text-white mt-1">{result.measurements.total_ms} ms</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Raw trace */}
        <details className="rounded-xl border border-[#1e1e2e] bg-[#12121a]/50 overflow-hidden">
          <summary className="px-4 py-3 text-sm font-medium text-[#9ca3af] cursor-pointer hover:text-white transition-colors select-none">
            Raw trace JSON
          </summary>
          <pre className="px-4 pb-4 text-xs font-mono text-[#9ca3af] overflow-x-auto whitespace-pre-wrap break-all max-h-96 overflow-y-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        </details>

        <div className="text-center pt-2">
          <Link href="/" className="text-sm text-[#6366f1] hover:text-[#818cf8] transition-colors">
            ← Back to inspection
          </Link>
        </div>
      </div>
    </div>
  );
}
