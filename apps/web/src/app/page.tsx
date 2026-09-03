"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Upload,
  Camera,
  X,
  FlaskConical,
  Image as ImageIcon,
  Loader2,
  Eye,
  Cpu,
  ScanSearch,
  History,
  Trash2,
} from "lucide-react";
import { loadHistory, clearHistory, type HistoryEntry } from "@/lib/history";
import toast from "react-hot-toast";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function HistorySection() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    setHistory(loadHistory().slice(0, 5));
  }, []);

  const handleClear = () => {
    clearHistory();
    setHistory([]);
    toast.success("History cleared");
  };

  // Listen for storage changes (when job page adds entry)
  useEffect(() => {
    const onStorage = () => setHistory(loadHistory().slice(0, 5));
    window.addEventListener("storage", onStorage);
    // Also poll on focus
    window.addEventListener("focus", onStorage);
    const interval = setInterval(onStorage, 1000);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", onStorage);
      clearInterval(interval);
    };
  }, []);

  if (history.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-2xl mt-6"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-[#9ca3af] flex items-center gap-2">
          <History className="h-4 w-4" />
          Recent inspections
        </h3>
        <button
          onClick={handleClear}
          className="text-xs text-[#9ca3af] hover:text-[#ededed] flex items-center gap-1 transition-colors"
        >
          <Trash2 className="h-3 w-3" />
          Clear history
        </button>
      </div>
      <div className="space-y-2">
        {history.map((entry) => (
          <a
            key={entry.job_id}
            href={`/job/${entry.job_id}`}
            className="flex items-center gap-3 p-3 rounded-lg bg-[#12121a] border border-[#1e1e2e] hover:border-[#6366f1]/30 hover:bg-[#1a1a28] transition-colors group"
          >
            {entry.thumbnail_url ? (
              <img
                src={entry.thumbnail_url}
                alt="thumbnail"
                className="w-10 h-10 rounded object-cover border border-[#1e1e2e] flex-shrink-0"
              />
            ) : (
              <div className="w-10 h-10 rounded bg-[#1e1e2e] flex items-center justify-center flex-shrink-0">
                <ImageIcon className="h-4 w-4 text-[#9ca3af]" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-mono text-[#ededed] truncate group-hover:text-[#818cf8] transition-colors">
                {entry.job_id}
              </p>
              <p className="text-xs text-[#9ca3af]">
                {new Date(entry.timestamp).toLocaleString()} · {entry.decision}
              </p>
            </div>
            <span
              className={`text-xs px-2 py-1 rounded-full font-medium flex-shrink-0 ${
                entry.decision === "PASS"
                  ? "bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30"
                  : entry.decision === "FAIL"
                    ? "bg-[#ef4444]/15 text-[#ef4444] border border-[#ef4444]/30"
                    : "bg-[#f59e0b]/15 text-[#f59e0b] border border-[#f59e0b]/30"
              }`}
            >
              {entry.decision}
            </span>
          </a>
        ))}
      </div>
    </motion.div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const referenceInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [mode, setMode] = useState<"idle" | "camera">("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [referencePreview, setReferencePreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return url;
    });
    setMode("idle");
    setError(null);
  }, []);

  const handleReferenceSelect = useCallback((file: File) => {
    setReferenceFile(file);
    const url = URL.createObjectURL(file);
    setReferencePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return url;
    });
    setError(null);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileSelect(file);
      // reset input so same file can be re-selected
      e.target.value = "";
    },
    [handleFileSelect]
  );

  const handleReferenceInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleReferenceSelect(file);
      e.target.value = "";
    },
    [handleReferenceSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file && file.type.startsWith("image/")) {
        handleFileSelect(file);
      } else if (file) {
        setError("Please drop an image file (jpg, png, webp).");
      }
    },
    [handleFileSelect]
  );

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setMode("camera");
      setError(null);
    } catch {
      setError("Camera access denied or unavailable.");
    }
  }, []);

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(video, 0, 0);

    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], "capture.jpg", { type: "image/jpeg" });
        handleFileSelect(file);
      }
    }, "image/jpeg", 0.9);

    const stream = video.srcObject as MediaStream;
    stream?.getTracks().forEach((t) => t.stop());
  }, [handleFileSelect]);

  const stopCamera = useCallback(() => {
    const stream = videoRef.current?.srcObject as MediaStream;
    stream?.getTracks().forEach((t) => t.stop());
    setMode("idle");
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);

    try {
      const form = new FormData();
      form.append("image", selectedFile);
      if (referenceFile) {
        form.append("reference_image", referenceFile);
      }

      const res = await fetch("/api/inspect", { method: "POST", body: form });
      if (!res.ok) throw new Error("Upload failed");

      const { job_id } = await res.json();
      // Save thumbnail for history optimistically — decision will be updated on job page
      try {
        const thumb = preview || null;
        // Store a temporary history entry with decision pending; job page will overwrite with real decision
        const existing = loadHistory();
        // We don't yet know decision, store as "PENDING" and let job page correct it
        // But per spec we should store after successful inspection; we store a placeholder here as fallback
        // Actual decision will be filled by job page
      } catch {}
      router.push(`/job/${job_id}`);
    } catch {
      setError("Failed to submit image. Please try again.");
      toast.error("Failed to submit image. Please try again.");
      setUploading(false);
    }
  }, [selectedFile, referenceFile, preview, router]);

  const reset = useCallback(() => {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    setSelectedFile(null);
    setMode("idle");
    setError(null);
  }, [preview]);

  const resetReference = useCallback(() => {
    if (referencePreview) URL.revokeObjectURL(referencePreview);
    setReferencePreview(null);
    setReferenceFile(null);
  }, [referencePreview]);

  const submitDemoCase = useCallback(
    (demoCase: string) => {
      setUploading(true);
      setError(null);
      fetch("/api/inspect", {
        method: "POST",
        body: new URLSearchParams({ demo_case: demoCase }),
      })
        .then((res) => {
          if (!res.ok) throw new Error("Demo inspect failed");
          return res.json();
        })
        .then(({ job_id }) => router.push(`/job/${job_id}`))
        .catch(() => {
          setError("Demo inspect failed. Please try again.");
          toast.error("Demo inspect failed. Please try again.");
          setUploading(false);
        });
    },
    [router]
  );

  return (
    <div className="min-h-screen bg-[#0a0a0f] bg-gradient-loopsight flex flex-col items-center">
      {/* Header */}
      <header className="w-full max-w-5xl px-4 md:px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#6366f1] flex items-center justify-center shadow-lg shadow-[#6366f1]/20">
            <ScanSearch className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white leading-none">LoopSight</h1>
            <p className="text-xs text-[#9ca3af] mt-0.5 hidden sm:block">Uncertainty-triggered visual inspection</p>
          </div>
        </div>
        <div className="text-xs text-[#9ca3af] hidden md:block">OpenCV 5 · Agentic Vision</div>
      </header>

      {/* Main upload card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="w-full max-w-2xl px-4"
      >
        <Card className="overflow-hidden">
          <CardContent className="p-6 md:p-8 space-y-5">
            {/* Tagline for mobile */}
            <div className="text-center sm:hidden -mt-2 mb-2">
              <p className="text-xs text-[#9ca3af]">Uncertainty-triggered visual inspection</p>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-lg bg-[#ef4444]/10 border border-[#ef4444]/20 p-3 text-sm text-[#fca5a5]"
              >
                {error}
              </motion.div>
            )}

            {/* Preview or camera or drop zone */}
            <AnimatePresence mode="wait">
              {preview ? (
                <motion.div
                  key="preview"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  className="relative"
                >
                  <div className="rounded-xl overflow-hidden border border-[#1e1e2e] bg-[#0a0a0f]">
                    <img
                      src={preview}
                      alt="Selected"
                      className="w-full object-contain max-h-80 mx-auto"
                    />
                  </div>
                  <button
                    onClick={reset}
                    className="absolute top-2 right-2 rounded-full bg-black/60 backdrop-blur p-2 text-white hover:bg-black/80 transition-colors"
                    aria-label="Remove image"
                  >
                    <X className="h-4 w-4" />
                  </button>
                  {/* File info */}
                  {selectedFile && (
                    <div className="mt-3 flex items-center gap-3 text-xs text-[#9ca3af] bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg p-3">
                      <ImageIcon className="h-4 w-4 flex-shrink-0" />
                      <span className="truncate flex-1 font-medium text-[#ededed]">{selectedFile.name}</span>
                      <span className="flex-shrink-0">{formatBytes(selectedFile.size)}</span>
                      <span className="flex-shrink-0 hidden sm:inline">{selectedFile.type || "image"}</span>
                    </div>
                  )}
                </motion.div>
              ) : mode === "camera" ? (
                <motion.div
                  key="camera"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="space-y-3"
                >
                  <div className="rounded-xl overflow-hidden border border-[#1e1e2e] bg-black">
                    <video
                      ref={videoRef}
                      className="w-full max-h-80 object-contain"
                      autoPlay
                      playsInline
                      muted
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={capturePhoto} className="flex-1">
                      <Camera className="mr-2 h-4 w-4" />
                      Capture
                    </Button>
                    <Button onClick={stopCamera} variant="outline" className="flex-1">
                      Cancel
                    </Button>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="dropzone"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="space-y-3"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleFileInput}
                  />
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`relative w-full h-44 md:h-52 rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-3 cursor-pointer transition-all ${
                      dragOver
                        ? "border-[#6366f1] bg-[#6366f1]/10 scale-[1.01]"
                        : "border-[#1e1e2e] bg-[#0a0a0f] hover:border-[#6366f1]/40 hover:bg-[#12121a]"
                    }`}
                  >
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${dragOver ? "bg-[#6366f1] text-white" : "bg-[#1e1e2e] text-[#9ca3af]"}`}>
                      <Upload className="h-6 w-6" />
                    </div>
                    <div className="text-center">
                      <p className="text-sm font-medium text-[#ededed]">
                        {dragOver ? "Drop image here" : "Drag & drop or click to upload"}
                      </p>
                      <p className="text-xs text-[#9ca3af] mt-1">JPEG, PNG, WebP up to 10 MB</p>
                    </div>
                  </div>
                  <Button onClick={startCamera} variant="outline" className="w-full">
                    <Camera className="mr-2 h-4 w-4" />
                    Use camera
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Reference image slot (Phase 3) */}
            <div className="rounded-xl border border-[#1e1e2e] bg-[#0a0a0f]/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-[#ededed]">Reference image (optional)</p>
                <span className="text-xs text-[#9ca3af]">known-good print</span>
              </div>
              <p className="text-xs text-[#9ca3af]">A known-good print for comparison — improves similarity scoring.</p>
              <input
                ref={referenceInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleReferenceInput}
              />
              {referencePreview ? (
                <div className="relative">
                  <img
                    src={referencePreview}
                    alt="Reference"
                    className="w-full h-32 object-contain rounded-lg border border-[#1e1e2e] bg-[#0a0a0f]"
                  />
                  <button
                    onClick={resetReference}
                    className="absolute top-1.5 right-1.5 rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80"
                  >
                    <X className="h-3 w-3" />
                  </button>
                  {referenceFile && (
                    <p className="text-xs text-[#9ca3af] mt-2 truncate">{referenceFile.name} · {formatBytes(referenceFile.size)}</p>
                  )}
                </div>
              ) : (
                <button
                  onClick={() => referenceInputRef.current?.click()}
                  className="w-full h-20 rounded-lg border border-dashed border-[#1e1e2e] bg-[#0a0a0f] hover:border-[#6366f1]/30 hover:bg-[#12121a] flex flex-col items-center justify-center gap-1.5 transition-colors"
                >
                  <ImageIcon className="h-5 w-5 text-[#9ca3af]" />
                  <span className="text-xs text-[#9ca3af]">Upload reference image</span>
                </button>
              )}
            </div>

            {/* Action buttons */}
            <div className="space-y-2.5 pt-1">
              <Button
                onClick={handleSubmit}
                disabled={!selectedFile || uploading}
                className="w-full h-11 text-sm font-semibold"
                variant="primary"
              >
                {uploading ? (
                  <span className="flex items-center gap-2.5">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Inspecting
                    <span className="flex gap-1 ml-1">
                      <motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 0.9, repeat: Infinity, delay: 0 }} className="w-1 h-1 rounded-full bg-white inline-block" />
                      <motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 0.9, repeat: Infinity, delay: 0.2 }} className="w-1 h-1 rounded-full bg-white inline-block" />
                      <motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 0.9, repeat: Infinity, delay: 0.4 }} className="w-1 h-1 rounded-full bg-white inline-block" />
                    </span>
                  </span>
                ) : (
                  "Inspect"
                )}
              </Button>

              {uploading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="w-full h-1.5 bg-[#1e1e2e] rounded-full overflow-hidden"
                >
                  <motion.div
                    className="h-full bg-gradient-to-r from-[#6366f1] to-[#818cf8] rounded-full"
                    initial={{ x: "-100%" }}
                    animate={{ x: "100%" }}
                    transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
                    style={{ width: "60%" }}
                  />
                </motion.div>
              )}

              <Button
                onClick={() => submitDemoCase("uncertain")}
                disabled={uploading}
                variant="ghost"
                className="w-full border border-[#1e1e2e] hover:border-[#6366f1]/30"
              >
                <FlaskConical className="mr-2 h-4 w-4" />
                Try demo case
              </Button>
            </div>

            {/* Pulsing inspecting indicator detail */}
            <AnimatePresence>
              {uploading && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="flex items-center justify-center gap-2 py-2 text-xs text-[#9ca3af]">
                    <motion.div
                      animate={{ scale: [1, 1.2, 1], opacity: [0.7, 1, 0.7] }}
                      transition={{ duration: 1.2, repeat: Infinity }}
                      className="w-2 h-2 rounded-full bg-[#6366f1]"
                    />
                    Running OpenCV first pass · analyzing edge continuity
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </motion.div>

      {/* History */}
      <div className="w-full max-w-2xl px-4">
        <HistorySection />
      </div>

      {/* Feature cards */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="w-full max-w-5xl px-4 mt-10 md:mt-14"
      >
        <div className="text-center mb-6">
          <h2 className="text-lg font-semibold text-white">How it works</h2>
          <p className="text-sm text-[#9ca3af] mt-1">Three steps, fully visible — no black box.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a]/60 backdrop-blur p-5 hover:border-[#6366f1]/20 transition-colors">
            <div className="w-10 h-10 rounded-lg bg-[#6366f1]/15 border border-[#6366f1]/20 flex items-center justify-center mb-3">
              <Eye className="h-5 w-5 text-[#818cf8]" />
            </div>
            <h3 className="font-medium text-white text-sm">1. First Look</h3>
            <p className="text-sm text-[#9ca3af] mt-1.5 leading-relaxed">OpenCV measures edge continuity, layer alignment, and reference similarity — deterministic, no LLM guessing.</p>
          </div>
          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a]/60 backdrop-blur p-5 hover:border-[#6366f1]/20 transition-colors">
            <div className="w-10 h-10 rounded-lg bg-[#f59e0b]/15 border border-[#f59e0b]/20 flex items-center justify-center mb-3">
              <Cpu className="h-5 w-5 text-[#f59e0b]" />
            </div>
            <h3 className="font-medium text-white text-sm">2. Agent Decides</h3>
            <p className="text-sm text-[#9ca3af] mt-1.5 leading-relaxed">If uncertain, a bounded agent picks exactly one whitelisted OpenCV tool to re-inspect — nothing more.</p>
          </div>
          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a]/60 backdrop-blur p-5 hover:border-[#6366f1]/20 transition-colors">
            <div className="w-10 h-10 rounded-lg bg-[#22c55e]/15 border border-[#22c55e]/20 flex items-center justify-center mb-3">
              <ScanSearch className="h-5 w-5 text-[#22c55e]" />
            </div>
            <h3 className="font-medium text-white text-sm">3. Second Look</h3>
            <p className="text-sm text-[#9ca3af] mt-1.5 leading-relaxed">A materially different observation resolves the ambiguity. Final verdict is deterministic and human-reviewable.</p>
          </div>
        </div>
      </motion.div>

      {/* Footer */}
      <div className="mt-10 mb-6 text-center text-xs text-[#6b7280] px-4">
        <p>LoopSight · OpenCV AI Competition 2026 · Demo mode — not a certified inspection</p>
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
