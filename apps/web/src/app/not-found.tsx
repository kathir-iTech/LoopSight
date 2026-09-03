import Link from "next/link";
import { SearchX, ArrowLeft, ScanSearch } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] bg-gradient-loopsight flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md text-center space-y-6">
        <div className="flex flex-col items-center gap-4">
          <div className="w-20 h-20 rounded-2xl bg-[#1e1e2e] border border-[#1e1e2e] flex items-center justify-center">
            <SearchX className="h-10 w-10 text-[#9ca3af]" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-white tracking-tight">Job not found</h1>
            <p className="text-sm text-[#9ca3af] leading-relaxed">
              The inspection you&apos;re looking for doesn&apos;t exist or may have expired. Jobs are stored in-memory and may not persist across deployments.
            </p>
          </div>
        </div>

        <div className="rounded-xl bg-[#12121a] border border-[#1e1e2e] p-4 flex items-start gap-3 text-left">
          <div className="w-8 h-8 rounded-lg bg-[#6366f1]/15 border border-[#6366f1]/20 flex items-center justify-center flex-shrink-0">
            <ScanSearch className="h-4 w-4 text-[#818cf8]" />
          </div>
          <div>
            <p className="text-sm font-medium text-white">What to do next</p>
            <p className="text-xs text-[#9ca3af] mt-1">Start a new inspection — upload a 3D print photo and see the evidence trace in seconds.</p>
          </div>
        </div>

        <Link href="/" className="inline-block w-full">
          <Button className="w-full" size="lg">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to inspection
          </Button>
        </Link>

        <p className="text-xs text-[#6b7280]">LoopSight · Uncertainty-triggered visual inspection</p>
      </div>
    </div>
  );
}
