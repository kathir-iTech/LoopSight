import Link from "next/link";

export default function CaptureGuide() {
  return <main className="mx-auto max-w-3xl space-y-7 px-5 py-10 text-slate-200">
    <Link href="/" className="text-sm text-sky-300 hover:underline">← Back to inspection</Link>
    <header className="space-y-3"><p className="text-xs uppercase tracking-widest text-sky-300">Controlled capture guide</p>
      <h1 className="text-3xl font-bold text-white">Give the camera a useful reference</h1>
      <p className="leading-relaxed text-slate-300">LoopSight measures how a checkerboard appears through a sample. Lighting, container shape, focus and framing affect that image. These instructions help collect comparable evidence; they do not calibrate physical turbidity.</p>
    </header>
    <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-4 text-amber-100">PASS means a high image-visibility score. It does not establish drinking-water safety. REVIEW means the evidence is insufficient.</div>
    <section className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-5"><h2 className="text-xl font-semibold">1. Prepare the target</h2>
      <p>Print the checkerboard on matte white paper. Keep all squares crisp and the page flat. This target provides contrast; it is not a certified measuring instrument or a physical crack-width scale.</p>
      <a href="/targets/checkerboard.svg" download="loopsight-checkerboard.svg" className="inline-block rounded-lg bg-sky-400 px-4 py-2 font-semibold text-slate-950">Download printable checkerboard</a>
      <img src="/targets/checkerboard.svg" alt="Eight by eight black-and-white checkerboard with a white border" className="mx-auto max-h-72 rounded bg-white" />
    </section>
    <section className="space-y-3"><h2 className="text-xl font-semibold">2. Take the first photo</h2>
      <ol className="list-decimal space-y-3 pl-5 leading-relaxed"><li>Place the target behind the transparent container so the pattern is visible through the sample. Fill most of the photo with the target and sample; avoid a large unrelated background.</li>
        <li>Hold the camera straight on, keep the target flat and tap to focus. Include the full visible water column if looking for vertical variation.</li>
        <li>Use a still photo without filters. Upload PNG, JPEG or WebP under 3.5 MB; image plus optional reference must fit the combined upload budget. The backend resizes analysis images to at most 1024 pixels per side.</li>
        <li>Read the result and its evidence. If the target is not detected, improve framing/focus and start again.</li></ol>
    </section>
    <section className="space-y-3"><h2 className="text-xl font-semibold">3. If requested, change the lighting</h2>
      <p>Keep the same sample, target and framing. Take a genuinely new photo: add diffuse backlight for a dim scene, or move a light to the side to avoid glare. Do not brighten or filter the first file and call it another capture.</p>
      <p>Use the follow-up control on the result page before its evidence expires. Duplicate, unrelated or poorly aligned images are rejected. A second image can still produce REVIEW; it does not have to resolve uncertainty.</p>
    </section>
    <section className="space-y-3 rounded-xl border border-slate-700 p-5"><h2 className="text-xl font-semibold">Understand what is retained</h2>
      <p>Raw analysis captures are accessible for 30 minutes by default. Result JSON and its diagnostic overlay remain accessible for up to 24 hours by default. Anyone with a result link may access the evidence that is still retained. Download an evidence ZIP to keep the images, policy snapshot and hash manifest; your downloaded copy does not expire with the server copy.</p>
      <p>For validation research, retain the original files separately and record preparation, device, session, lighting and independent labels. Do not label the generated test presets as physical captures.</p>
      <Link href="/evaluation" className="inline-block text-sky-300 hover:underline">See the measured results and current limitations →</Link>
    </section>
  </main>;
}
