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
  Droplets,
  Eye,
  Sun,
  ChevronDown,
  Image as ImageIcon,
  History,
  Trash2,
  Waves,
  Sparkles,
  Layers,
  Ruler,
  Cpu,
} from "lucide-react";
import { loadHistory, clearHistory, type HistoryEntry } from "@/lib/history";
import toast from "react-hot-toast";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

interface PreflightMetrics {
  width: number;
  height: number;
  contrast: number;
  glarePct: number;
}

const BENCHMARK_CASES = [
  {
    id: "water_glare_confounded",
    title: "Clear Water + Specular Glare",
    profile: "water_turbidity_v1",
    badge: "inpaint_specular_glare → PASS",
    desc: "Curved glass reflection washes out Pass 1 (UNCERTAIN). Agent runs Telea glare inpainting + dynamic contrast recovery.",
  },
  {
    id: "water_stratified_sediment",
    title: "Settled Bottom Sediment",
    profile: "water_turbidity_v1",
    badge: "analyze_vertical_stratification → FAIL",
    desc: "Clear upper supernatant masks dense bottom mud (Δ=0.47). Agent runs 3-zone vertical nephelometry to catch settled turbidity.",
  },
  {
    id: "water_dual_lighting",
    title: "Ambient → Backlight Pair",
    profile: "water_turbidity_v1",
    badge: "track_across_frames → PASS",
    desc: "Dim ambient capture scores UNCERTAIN (0.31). Agent fuses backlit second frame (0.79) with sub-pixel registration.",
  },
  {
    id: "water_turbid_fail",
    title: "High-Turbidity Colloidal Sample",
    profile: "water_turbidity_v1",
    badge: "Pass 1 Confident → FAIL",
    desc: "Heavy suspended turbidity blurs checkerboard (0.11 ≤ 0.20). Immediate deterministic FAIL without wasting agent compute.",
  },
  {
    id: "crack_shadow_confounded",
    title: "Concrete + Surface Glare/Shadow",
    profile: "structural_crack_metrology_v1",
    badge: "skeletonize_crack_metrology → PASS",
    desc: "Surface artifact mimics fracture on Pass 1. Agent runs homomorphic illumination normalization + distance transform (0.00mm).",
  },
  {
    id: "crack_structural_fail",
    title: "Structural Concrete Crack (0.72mm)",
    profile: "structural_crack_metrology_v1",
    badge: "Pass 1 Metrology → FAIL",
    desc: "Morphological black-hat + Euclidean distance transform (cv2.distanceTransform) measures 0.719mm fracture width.",
  },
];

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
  useEffect(() => {
    const onStorage = () => setHistory(loadHistory().slice(0, 5));
    window.addEventListener("storage", onStorage);
    window.addEventListener("focus", onStorage);
    const iv = setInterval(onStorage, 1000);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", onStorage);
      clearInterval(iv);
    };
  }, []);
  if (history.length === 0) return null;
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-2xl mt-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-[#8aa0c0] flex items-center gap-2">
          <History className="h-4 w-4" />
          Recent inspections
        </h3>
        <button
          onClick={handleClear}
          className="text-xs text-[#8aa0c0] hover:text-[#e6f0ff] flex items-center gap-1 transition-colors"
        >
          <Trash2 className="h-3 w-3" />
          Clear
        </button>
      </div>
      <div className="space-y-2">
        {history.map((entry) => (
          <a
            key={entry.job_id}
            href={`/job/${entry.job_id}`}
            className="flex items-center gap-3 p-3 rounded-xl bg-[#0f2942]/60 border border-[#1e3a5f] hover:border-[#38bdf8]/30 hover:bg-[#12365a]/60 transition-colors group"
          >
            <div className="w-9 h-9 rounded-lg bg-[#0a1628] border border-[#1e3a5f] flex items-center justify-center flex-shrink-0">
              <Droplets className="h-4 w-4 text-[#38bdf8]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-mono text-[#e6f0ff] truncate group-hover:text-[#7dd3fc] transition-colors">
                {entry.job_id}
              </p>
              <p className="text-xs text-[#8aa0c0]">
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

function DropletLoader() {
  return (
    <div className="flex flex-col items-center gap-3 py-4">
      <div className="relative w-20 h-24 flex items-end justify-center">
        <svg width={64} height={84} viewBox="0 0 64 84" className="absolute inset-0 mx-auto">
          <path
            d="M32 4 C 32 4 12 26 12 46 C 12 62 20 72 32 72 C 44 72 52 62 52 46 C 52 26 32 4 32 4 Z"
            fill="none"
            stroke="rgba(56,189,248,0.35)"
            strokeWidth={1.5}
          />
        </svg>
        <motion.div
          className="absolute bottom-[12px] left-1/2 -translate-x-1/2 w-[40px] rounded-b-[18px] overflow-hidden"
          initial={{ height: 2 }}
          animate={{ height: 54 }}
          transition={{ duration: 1.4, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
          style={{ background: "linear-gradient(to top, #0ea5e9 0%, #38bdf8 45%, #7dd3fc 100%)" }}
        >
          <motion.div
            className="absolute top-0 left-0 right-0 h-[8px]"
            style={{ background: "rgba(255,255,255,0.35)", borderRadius: "50% 50% 0 0 / 100% 100% 0 0" }}
            animate={{ x: ["-8px", "8px", "-8px"] }}
            transition={{ duration: 1.0, repeat: Infinity, ease: "easeInOut" }}
          />
        </motion.div>
        <motion.div
          className="absolute bottom-[6px] left-1/2 -translate-x-1/2 w-3 h-3 rounded-full border border-[#38bdf8]/50"
          animate={{ scale: [0.8, 1.8], opacity: [0.6, 0] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
        />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-[#38bdf8] flex items-center justify-center gap-2">
          <motion.span animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.2, repeat: Infinity }}>
            <Waves className="h-4 w-4" />
          </motion.span>
          Running OpenCV 5 active perception...
        </p>
        <p className="text-xs text-[#8aa0c0] mt-1">Measuring pattern visibility, glare, stratification & geometry</p>
      </div>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const referenceInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [selectedProfile, setSelectedProfile] = useState<string>("water_turbidity_v1");
  const [mode, setMode] = useState<"idle" | "camera">("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preflight, setPreflight] = useState<PreflightMetrics | null>(null);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [referencePreview, setReferencePreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const computeClientPreflight = useCallback((url: string) => {
    const img = new window.Image();
    img.onload = () => {
      try {
        const c = document.createElement("canvas");
        const w = Math.min(200, img.width || 200);
        const h = Math.min(200, img.height || 200);
        c.width = w;
        c.height = h;
        const ctx = c.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(img, 0, 0, w, h);
        const data = ctx.getImageData(0, 0, w, h).data;
        let sum = 0;
        let sumSq = 0;
        let glare = 0;
        const n = w * h;
        for (let i = 0; i < data.length; i += 4) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          const lum = 0.299 * r + 0.587 * g + 0.114 * b;
          sum += lum;
          sumSq += lum * lum;
          if (r > 240 && g > 240 && b > 240) glare++;
        }
        const mean = sum / n;
        const std = Math.sqrt(Math.max(0, sumSq / n - mean * mean));
        setPreflight({
          width: img.width,
          height: img.height,
          contrast: Number((std / 128).toFixed(3)),
          glarePct: Number(((glare / n) * 100).toFixed(1)),
        });
      } catch {
        setPreflight(null);
      }
    };
    img.src = url;
  }, []);

  const handleFileSelect = useCallback(
    (file: File) => {
      if (file.size > 10 * 1024 * 1024) {
        setError("Image file exceeds 10 MB limit. Please choose a smaller photo.");
        return;
      }
      setSelectedFile(file);
      const url = URL.createObjectURL(file);
      setPreview((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return url;
      });
      computeClientPreflight(url);
      setMode("idle");
      setError(null);
    },
    [computeClientPreflight]
  );

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
      if (file && file.type.startsWith("image/")) handleFileSelect(file);
      else if (file) setError("Please drop an image file (jpg, png, webp).");
    },
    [handleFileSelect]
  );

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
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
    canvas.toBlob(
      (blob) => {
        if (blob) {
          const file = new File([blob], "capture.jpg", { type: "image/jpeg" });
          handleFileSelect(file);
        }
      },
      "image/jpeg",
      0.9
    );
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
      form.append("inspection_profile", selectedProfile);
      if (referenceFile) form.append("reference_image", referenceFile);
      const res = await fetch("/api/inspect", { method: "POST", body: form });
      if (!res.ok) throw new Error("Upload failed");
      const { job_id } = await res.json();
      router.push(`/job/${job_id}`);
    } catch {
      setError("Failed to submit image. Please try again.");
      toast.error("Failed to submit image. Please try again.");
      setUploading(false);
    }
  }, [selectedFile, referenceFile, selectedProfile, router]);

  const runBenchmarkSample = useCallback(
    async (sampleId: string, profile: string) => {
      setUploading(true);
      setError(null);
      try {
        const form = new FormData();
        form.append("sample_id", sampleId);
        form.append("inspection_profile", profile);
        const res = await fetch("/api/inspect", { method: "POST", body: form });
        if (!res.ok) throw new Error("Sample inspection failed");
        const { job_id } = await res.json();
        router.push(`/job/${job_id}`);
      } catch {
        setError("Failed to run benchmark sample.");
        toast.error("Failed to run benchmark sample.");
        setUploading(false);
      }
    },
    [router]
  );

  const reset = useCallback(() => {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    setSelectedFile(null);
    setPreflight(null);
    setMode("idle");
    setError(null);
  }, [preview]);

  const resetReference = useCallback(() => {
    if (referencePreview) URL.revokeObjectURL(referencePreview);
    setReferencePreview(null);
    setReferenceFile(null);
  }, [referencePreview]);

  return (
    <div className="min-h-screen bg-[#0a1628] flex flex-col items-center relative overflow-hidden">
      <div className="ripple-bg" aria-hidden>
        <div className="ripple-wave ripple-wave-1" />
        <div className="ripple-wave ripple-wave-2" />
        <div className="ripple-wave-3" />
        <div className="wave-line" style={{ top: "28%" }} />
        <div className="wave-line" style={{ top: "72%", animationDelay: "2s" }} />
      </div>

      {/* Header */}
      <header className="w-full max-w-5xl px-4 md:px-6 py-5 flex items-center justify-between relative z-10">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#0ea5e9] to-[#38bdf8] flex items-center justify-center shadow-lg shadow-[#38bdf8]/20">
            <Droplets className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-[19px] font-semibold tracking-tight text-white leading-none">LoopSight v2</h1>
            <p className="text-[11px] text-[#8aa0c0] mt-0.5 hidden sm:block tracking-wide">
              Active-Perception Optical Nephelometry & Spatial Metrology
            </p>
          </div>
        </div>
        <div className="text-[11px] text-[#8aa0c0] hidden md:flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-full bg-[#0f2942] border border-[#1e3a5f] text-[#38bdf8] flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5" />
            OpenCV 5 · 8 MCP Tools · AWS Lambda ARM64
          </span>
        </div>
      </header>

      {/* Safety banner — FIRST screen, never footer-only */}
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="w-full max-w-2xl px-4 relative z-10"
      >
        <div className="rounded-xl bg-[#38bdf8]/10 border border-[#38bdf8]/20 px-4 py-3 flex gap-2.5 items-start">
          <div className="w-6 h-6 rounded-full bg-[#38bdf8]/15 border border-[#38bdf8]/20 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Droplets className="h-3.5 w-3.5 text-[#38bdf8]" />
          </div>
          <div>
            <p className="text-[13px] leading-relaxed text-[#e6f0ff]">
              <span className="font-medium">Flags visibly cloudy water for follow-up.</span>{" "}
              <span className="text-[#8aa0c0]">
                Not a substitute for a real water safety test. Clear-looking water can still carry invisible
                contaminants — arsenic, fluoride, nitrate — that no camera can see.
              </span>
            </p>
          </div>
        </div>
      </motion.div>

      {/* Headline */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.5 }}
        className="w-full max-w-2xl px-4 mt-6 text-center relative z-10"
      >
        <h2 className="text-[28px] md:text-[33px] font-bold tracking-tight text-white leading-tight">
          Check your water{" "}
          <span className="bg-gradient-to-r from-[#38bdf8] to-[#7dd3fc] bg-clip-text text-transparent">
            before you drink it.
          </span>
        </h2>
        <p className="text-[13.5px] text-[#8aa0c0] mt-2.5 leading-relaxed max-w-[560px] mx-auto">
          Uncertainty-triggered OpenCV 5 active perception: when glass glare, settling sediment, shadow, or dim lighting
          confounds the first look, our bounded agent dispatches a specialized second-look CV tool (+0.75 conditional
          benefit over single-pass).
        </p>
      </motion.div>

      {/* Main Upload Workbench */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.22, duration: 0.5, ease: "easeOut" }}
        className="w-full max-w-2xl px-4 mt-6 relative z-10"
      >
        <Card className="overflow-hidden border-[#1e3a5f]/70 bg-[#0f2942]/80 backdrop-blur-xl">
          <CardContent className="p-5 md:p-6 space-y-4">
            {/* Profile Switcher Pills */}
            <div className="grid grid-cols-3 gap-2 p-1 rounded-xl bg-[#0a1628] border border-[#1e3a5f]">
              <button
                type="button"
                onClick={() => setSelectedProfile("water_turbidity_v1")}
                className={`py-2 px-2.5 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-all ${
                  selectedProfile === "water_turbidity_v1"
                    ? "bg-[#38bdf8] text-[#0a1628] shadow"
                    : "text-[#8aa0c0] hover:text-white"
                }`}
              >
                <Droplets className="h-3.5 w-3.5" />
                <span className="truncate">Water Nephelometry</span>
              </button>
              <button
                type="button"
                onClick={() => setSelectedProfile("structural_crack_metrology_v1")}
                className={`py-2 px-2.5 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-all ${
                  selectedProfile === "structural_crack_metrology_v1"
                    ? "bg-[#38bdf8] text-[#0a1628] shadow"
                    : "text-[#8aa0c0] hover:text-white"
                }`}
              >
                <Ruler className="h-3.5 w-3.5" />
                <span className="truncate">Crack Metrology (mm)</span>
              </button>
              <button
                type="button"
                onClick={() => setSelectedProfile("fdm_print_surface_v1")}
                className={`py-2 px-2.5 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-all ${
                  selectedProfile === "fdm_print_surface_v1"
                    ? "bg-[#38bdf8] text-[#0a1628] shadow"
                    : "text-[#8aa0c0] hover:text-white"
                }`}
              >
                <Layers className="h-3.5 w-3.5" />
                <span className="truncate">Surface Edge QC</span>
              </button>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-xl bg-[#ef4444]/10 border border-[#ef4444]/20 p-3 text-sm text-[#fca5a5]"
              >
                {error}
              </motion.div>
            )}

            <AnimatePresence mode="wait">
              {preview ? (
                <motion.div
                  key="preview"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  className="relative"
                >
                  <div className="rounded-2xl overflow-hidden border border-[#1e3a5f] bg-[#0a1628]">
                    <img src={preview} alt="Selected" className="w-full object-contain max-h-[300px] mx-auto" />
                  </div>
                  <button
                    onClick={reset}
                    className="absolute top-2.5 right-2.5 rounded-full bg-black/60 backdrop-blur p-2 text-white hover:bg-black/80 transition-colors"
                    aria-label="Remove image"
                  >
                    <X className="h-4 w-4" />
                  </button>
                  {selectedFile && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center gap-3 text-xs text-[#8aa0c0] bg-[#0a1628] border border-[#1e3a5f] rounded-xl p-3">
                        <ImageIcon className="h-4 w-4 flex-shrink-0 text-[#38bdf8]" />
                        <span className="truncate flex-1 font-medium text-[#e6f0ff]">{selectedFile.name}</span>
                        <span className="flex-shrink-0">{formatBytes(selectedFile.size)}</span>
                      </div>
                      {preflight && (
                        <div className="grid grid-cols-3 gap-2 text-[11px] bg-[#0a1628]/80 border border-[#1e3a5f]/70 rounded-xl p-2.5">
                          <div>
                            <span className="text-[#8aa0c0] block">Dimensions</span>
                            <span className="font-mono text-[#e6f0ff]">
                              {preflight.width}×{preflight.height}px
                            </span>
                          </div>
                          <div>
                            <span className="text-[#8aa0c0] block">Pre-flight Contrast</span>
                            <span className="font-mono text-[#38bdf8]">{preflight.contrast}</span>
                          </div>
                          <div>
                            <span className="text-[#8aa0c0] block">Specular Glare</span>
                            <span
                              className={`font-mono ${
                                preflight.glarePct >= 3.0 ? "text-[#f59e0b]" : "text-[#22c55e]"
                              }`}
                            >
                              {preflight.glarePct}%
                            </span>
                          </div>
                        </div>
                      )}
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
                  <div className="rounded-2xl overflow-hidden border border-[#1e3a5f] bg-black">
                    <video ref={videoRef} className="w-full max-h-80 object-contain" autoPlay playsInline muted />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={capturePhoto}
                      className="flex-1 bg-[#38bdf8] hover:bg-[#0ea5e9] text-[#0a1628] font-semibold shadow-lg shadow-[#38bdf8]/20"
                    >
                      <Camera className="mr-2 h-4 w-4" />
                      Capture
                    </Button>
                    <Button
                      onClick={stopCamera}
                      variant="outline"
                      className="flex-1 border-[#1e3a5f] text-[#e6f0ff] hover:bg-[#0f2942]"
                    >
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
                  className="space-y-2.5"
                >
                  <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileInput} />
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`relative w-full h-[176px] rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-2.5 cursor-pointer transition-all ${
                      dragOver
                        ? "border-[#38bdf8] bg-[#38bdf8]/10 scale-[1.01]"
                        : "border-[#1e3a5f] bg-[#0a1628]/60 hover:border-[#38bdf8]/40 hover:bg-[#0f2942]/40"
                    }`}
                  >
                    <div
                      className={`w-11 h-11 rounded-2xl flex items-center justify-center transition-colors ${
                        dragOver
                          ? "bg-[#38bdf8] text-white shadow-lg shadow-[#38bdf8]/20"
                          : "bg-[#0f2942] text-[#38bdf8] border border-[#1e3a5f]"
                      }`}
                    >
                      <Upload className="h-5 w-5" />
                    </div>
                    <div className="text-center">
                      <p className="text-[14px] font-medium text-[#e6f0ff]">
                        {dragOver ? "Drop image here" : "Drop photo or click to upload"}
                      </p>
                      <p className="text-xs text-[#8aa0c0] mt-0.5">
                        {selectedProfile === "water_turbidity_v1"
                          ? "Checkerboard behind water · JPEG/PNG/WebP ≤10 MB"
                          : selectedProfile === "structural_crack_metrology_v1"
                          ? "Concrete/wall surface photo · measures fracture width in mm"
                          : "3D-print or hardware surface photo · edge & reference QC"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        startCamera();
                      }}
                      className="text-xs text-[#38bdf8] hover:text-[#7dd3fc] flex items-center gap-1.5 transition-colors"
                    >
                      <Camera className="h-3.5 w-3.5" />
                      Use camera instead
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Primary Inspect CTA */}
            <div className="space-y-3 pt-1">
              <Button
                onClick={handleSubmit}
                disabled={!selectedFile || uploading}
                className="w-full h-[46px] text-sm font-semibold bg-[#38bdf8] hover:bg-[#0ea5e9] text-[#0a1628] shadow-lg shadow-[#38bdf8]/20 disabled:opacity-40 disabled:shadow-none"
              >
                {uploading ? "Running OpenCV 5 pipeline..." : "Run Active-Perception Inspection"}
              </Button>
              <AnimatePresence>
                {uploading && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <DropletLoader />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Advanced options */}
            <div className="pt-2 border-t border-[#1e3a5f]/50">
              <button
                type="button"
                onClick={() => setAdvancedOpen(!advancedOpen)}
                className="w-full flex items-center justify-between text-xs text-[#8aa0c0] hover:text-[#e6f0ff] transition-colors py-1.5"
              >
                <span className="flex items-center gap-2">
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform ${advancedOpen ? "rotate-180" : ""}`} />
                  Advanced options (Reference image)
                </span>
                <span className="text-[11px]">{advancedOpen ? "Hide" : "Expand"}</span>
              </button>
              <AnimatePresence>
                {advancedOpen && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="pt-3 space-y-3">
                      <div className="rounded-xl border border-[#1e3a5f] bg-[#0a1628]/50 p-3.5 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-medium text-[#e6f0ff]">Reference image (optional)</p>
                          <span className="text-[11px] text-[#8aa0c0]">known-good baseline</span>
                        </div>
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
                              className="w-full h-28 object-contain rounded-lg border border-[#1e3a5f] bg-[#0a1628]"
                            />
                            <button
                              type="button"
                              onClick={resetReference}
                              className="absolute top-1.5 right-1.5 rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => referenceInputRef.current?.click()}
                            className="w-full h-14 rounded-lg border border-dashed border-[#1e3a5f] bg-[#0a1628] hover:border-[#38bdf8]/30 flex flex-col items-center justify-center gap-1 transition-colors"
                          >
                            <ImageIcon className="h-4 w-4 text-[#8aa0c0]" />
                            <span className="text-[11px] text-[#8aa0c0]">Upload reference baseline</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* 1-Click Judge Live Test Bench — No Printer Needed */}
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.28, duration: 0.5 }}
        className="w-full max-w-3xl px-4 mt-7 relative z-10"
      >
        <div className="rounded-2xl border border-[#1e3a5f]/70 bg-[#0f2942]/60 backdrop-blur-xl p-5">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3.5">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#38bdf8]" />
                1-Click Live OpenCV 5 Benchmark Test Bench
              </h3>
              <p className="text-xs text-[#8aa0c0] mt-0.5">
                Test any physics-calibrated scenario through the real OpenCV 5 + Agent pipeline immediately (no printer required).
              </p>
            </div>
            <span className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-[#38bdf8]/15 border border-[#38bdf8]/30 text-[#38bdf8]">
              Conditional Benefit: +0.7500
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {BENCHMARK_CASES.map((item) => (
              <button
                key={item.id}
                type="button"
                disabled={uploading}
                onClick={() => runBenchmarkSample(item.id, item.profile)}
                className="text-left p-3.5 rounded-xl bg-[#0a1628]/80 border border-[#1e3a5f] hover:border-[#38bdf8]/50 hover:bg-[#0f2942] transition-all group disabled:opacity-50"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-white group-hover:text-[#38bdf8] transition-colors">
                    {item.title}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-[#0f2942] border border-[#1e3a5f] text-[#7dd3fc]">
                    {item.badge}
                  </span>
                </div>
                <p className="text-[11px] text-[#8aa0c0] mt-1.5 leading-relaxed">{item.desc}</p>
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* History */}
      <div className="w-full max-w-2xl px-4 relative z-10">
        <HistorySection />
      </div>

      {/* How it works stepper */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.34, duration: 0.5 }}
        className="w-full max-w-3xl px-4 mt-7 relative z-10"
      >
        <div className="rounded-2xl border border-[#1e3a5f]/60 bg-[#0f2942]/50 backdrop-blur-xl p-5 md:p-6">
          <div className="text-center mb-5">
            <h2 className="text-[15px] font-semibold text-white">How Active Perception Works</h2>
            <p className="text-xs text-[#8aa0c0] mt-1">
              OpenCV 5 measures evidence; the bounded agent only selects which OpenCV tool runs next; policy.py decides.
            </p>
          </div>
          <div className="flex flex-col md:flex-row gap-4 md:gap-0 md:items-start">
            <div className="flex-1 flex gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#38bdf8]/15 border border-[#38bdf8]/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Eye className="h-4 w-4 text-[#38bdf8]" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-white">1 · First-Pass OpenCV 5</h3>
                <p className="text-xs text-[#8aa0c0] mt-1 leading-relaxed">
                  Measures pattern visibility, specular glare %, perspective skew, 3-zone stratification, or fracture width (mm).
                </p>
              </div>
            </div>
            <div className="hidden md:flex items-center justify-center px-2 pt-3">
              <div className="w-8 h-px bg-[#1e3a5f]" />
              <div className="w-1.5 h-1.5 rounded-full bg-[#38bdf8]/40 mx-1" />
              <div className="w-8 h-px bg-[#1e3a5f]" />
            </div>
            <div className="flex-1 flex gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#f59e0b]/15 border border-[#f59e0b]/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Sun className="h-4 w-4 text-[#f59e0b]" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-white">2 · Agent Selects CV Tool</h3>
                <p className="text-xs text-[#8aa0c0] mt-1 leading-relaxed">
                  When confounded, the agent dispatches Telea glare inpainting, homography deskew, vertical stratification, or backlight fusion.
                </p>
              </div>
            </div>
            <div className="hidden md:flex items-center justify-center px-2 pt-3">
              <div className="w-8 h-px bg-[#1e3a5f]" />
              <div className="w-1.5 h-1.5 rounded-full bg-[#38bdf8]/40 mx-1" />
              <div className="w-8 h-px bg-[#1e3a5f]" />
            </div>
            <div className="flex-1 flex gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#22c55e]/15 border border-[#22c55e]/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Droplets className="h-4 w-4 text-[#22c55e]" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-white">3 · Deterministic Verdict</h3>
                <p className="text-xs text-[#8aa0c0] mt-1 leading-relaxed">
                  Clear → “no visible turbidity, does not confirm safe.” Cloudy → “do not drink without treatment.” Borderline stays{" "}
                  <span className="text-[#f59e0b]">REVIEW</span>.
                </p>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Footer */}
      <div className="mt-8 mb-6 text-center px-4 relative z-10">
        <p className="text-[11px] leading-relaxed text-[#8aa0c0] max-w-2xl">
          LoopSight flags <span className="text-[#7dd3fc] font-medium">visibly cloudy water</span> and{" "}
          <span className="text-[#7dd3fc] font-medium">structural surface fractures</span> for follow-up. It does not
          confirm water is safe — invisible contaminants require a real water test.
        </p>
        <p className="text-[11px] text-[#5a7aa0] mt-2">
          OpenCV AI Competition 2026 · Built for rural groundwater & infrastructure screening.
        </p>
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
