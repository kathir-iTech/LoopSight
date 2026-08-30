"use client";

import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Upload, Camera, X } from "lucide-react";

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [mode, setMode] = useState<"idle" | "camera">("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreview(url);
    setMode("idle");
    setError(null);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileSelect(file);
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

      const res = await fetch("/api/inspect", { method: "POST", body: form });
      if (!res.ok) throw new Error("Upload failed");

      const { job_id } = await res.json();
      router.push(`/job/${job_id}`);
    } catch {
      setError("Failed to submit image. Please try again.");
      setUploading(false);
    }
  }, [selectedFile, router]);

  const reset = useCallback(() => {
    setPreview(null);
    setSelectedFile(null);
    setMode("idle");
    setError(null);
  }, []);

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">LoopSight</CardTitle>
          <CardDescription>
            Upload a 3D print photo or capture one to inspect
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {preview ? (
            <div className="relative">
              <img
                src={preview}
                alt="Selected"
                className="w-full rounded-lg object-contain max-h-80"
              />
              <button
                onClick={reset}
                className="absolute top-2 right-2 rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : mode === "camera" ? (
            <div className="space-y-3">
              <video
                ref={videoRef}
                className="w-full rounded-lg"
                autoPlay
                playsInline
                muted
              />
              <div className="flex gap-2">
                <Button onClick={capturePhoto} className="flex-1">
                  <Camera className="mr-2 h-4 w-4" />
                  Capture
                </Button>
                <Button onClick={stopCamera} variant="outline" className="flex-1">
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileInput}
              />
              <Button
                onClick={() => fileInputRef.current?.click()}
                variant="outline"
                className="w-full h-32 border-dashed"
              >
                <Upload className="mr-2 h-5 w-5" />
                Choose a photo
              </Button>
              <Button onClick={startCamera} variant="outline" className="w-full">
                <Camera className="mr-2 h-4 w-4" />
                Use camera
              </Button>
            </div>
          )}

          <Button
            onClick={handleSubmit}
            disabled={!selectedFile || uploading}
            className="w-full"
          >
            {uploading ? "Inspecting..." : "Inspect"}
          </Button>
        </CardContent>
      </Card>
      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
