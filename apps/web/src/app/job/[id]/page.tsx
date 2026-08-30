"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { InspectionResult } from "@/lib/types";

function DecisionCard({ result }: { result: InspectionResult }) {
  const { decision, confidence_band, human_approval_required } =
    result.final_decision;

  const colorMap: Record<string, { bg: string; border: string; text: string; badge: "success" | "warning" | "destructive" }> = {
    PASS: {
      bg: "bg-green-50",
      border: "border-green-300",
      text: "text-green-800",
      badge: "success",
    },
    REVIEW: {
      bg: "bg-yellow-50",
      border: "border-yellow-300",
      text: "text-yellow-800",
      badge: "warning",
    },
    FAIL: {
      bg: "bg-red-50",
      border: "border-red-300",
      text: "text-red-800",
      badge: "destructive",
    },
  };

  const c = colorMap[decision];

  return (
    <Card className={`${c.bg} ${c.border}`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className={`text-lg ${c.text}`}>Final Decision</CardTitle>
          <Badge variant={c.badge} className="text-base px-3 py-1">
            {decision}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p>
          Confidence: <span className="font-medium">{confidence_band}</span>
        </p>
        <p>
          Human approval required:{" "}
          <span className="font-medium">
            {human_approval_required ? "Yes" : "No"}
          </span>
        </p>
      </CardContent>
    </Card>
  );
}

export default function JobPage() {
  const params = useParams();
  const id = params.id as string;

  const [result, setResult] = useState<InspectionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/jobs/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Job not found");
        return r.json();
      })
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <p className="text-neutral-500">Loading job...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center gap-4">
        <p className="text-red-600">{error || "Job not found"}</p>
        <Link href="/">
          <Button variant="outline">Back to upload</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50 p-4 md:p-8">
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Evidence Trace</h1>
          <div className="flex items-center gap-3">
            <Badge variant="outline">Job {id}</Badge>
            <Link href="/">
              <Button variant="ghost" size="sm">
                New inspection
              </Button>
            </Link>
          </div>
        </div>

        {/* Section 1: Perception */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">1. Perception</CardTitle>
              <Badge variant="secondary">{result.status}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.evidence_gap.length > 0 && (
              <div className="rounded-md bg-amber-50 p-3 text-sm">
                <p className="font-medium text-amber-800 mb-1">Evidence gaps:</p>
                <ul className="list-disc list-inside text-amber-700">
                  {result.evidence_gap.map((gap, i) => (
                    <li key={i}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.regions.map((region, i) => (
              <div key={i} className="rounded-md bg-neutral-50 p-3">
                <p className="text-xs text-neutral-500 mb-2">
                  Region ({region.x}, {region.y}) &times; {region.w}&times;
                  {region.h}
                </p>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <p className="text-neutral-500">Edge continuity</p>
                    <p className="font-mono font-medium">
                      {region.evidence.edge_continuity.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-neutral-500">Ref. similarity</p>
                    <p className="font-mono font-medium">
                      {region.evidence.reference_similarity.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-neutral-500">Layer align. dev.</p>
                    <p className="font-mono font-medium">
                      {region.evidence.layer_alignment_deviation.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Section 2: Agent Decision */}
        {result.agent_call && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">2. Agent Decision</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md bg-blue-50 p-3 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-blue-600">Tool selected</p>
                    <p className="font-mono font-medium text-blue-800">
                      {result.agent_call.tool}
                    </p>
                  </div>
                  <div>
                    <p className="text-blue-600">Reason code</p>
                    <p className="font-mono font-medium text-blue-800">
                      {result.agent_call.reason_code}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Section 3: New Evidence */}
        {result.second_pass && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">3. New Evidence</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {result.second_pass.regions.map((region, i) => (
                  <div key={i} className="rounded-md bg-neutral-50 p-3 text-sm">
                    <p className="text-xs text-neutral-500 mb-1">
                      Second-pass region {i + 1}
                    </p>
                    <div className="flex flex-wrap gap-4">
                      {Object.entries(region).map(([key, val]) => (
                        <div key={key}>
                          <p className="text-neutral-500">
                            {key.replace(/_/g, " ")}
                          </p>
                          <p className="font-mono font-medium">
                            {typeof val === "number" ? val.toFixed(2) : val}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Section 4: Final Decision */}
        <DecisionCard result={result} />
      </div>
    </div>
  );
}
