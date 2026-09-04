import Link from "next/link";
import { SearchX, ArrowLeft, Droplets } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0a1628] bg-gradient-loopsight flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md text-center space-y-6">
        <div className="flex flex-col items-center gap-4">
          <div className="w-20 h-20 rounded-2xl bg-[#0f2942] border border-[#1e3a5f] flex items-center justify-center">
            <SearchX className="h-10 w-10 text-[#8aa0c0]" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-white tracking-tight">Not found</h1>
            <p className="text-sm text-[#8aa0c0] leading-relaxed">
              The check you&apos;re looking for doesn&apos;t exist or may have expired. Checks are stored in-memory and may not persist across deployments.
            </p>
          </div>
        </div>

        <div className="rounded-xl bg-[#0f2942]/60 border border-[#1e3a5f] p-4 flex items-start gap-3 text-left">
          <div className="w-8 h-8 rounded-lg bg-[#38bdf8]/15 border border-[#38bdf8]/20 flex items-center justify-center flex-shrink-0">
            <Droplets className="h-4 w-4 text-[#38bdf8]" />
          </div>
          <div>
            <p className="text-sm font-medium text-white">What to do next</p>
            <p className="text-xs text-[#8aa0c0] mt-1">Start a new clarity check — photograph a checkerboard through water and see the trace in seconds.</p>
          </div>
        </div>

        <Link href="/" className="inline-block w-full">
          <Button className="w-full" size="lg">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to water check
          </Button>
        </Link>

        <p className="text-xs text-[#5a7aa0]">LoopSight · Flags visibly cloudy water · not a substitute for a lab test</p>
      </div>
    </div>
  );
}
