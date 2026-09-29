import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-24 text-center">
      <p className="eyebrow">Red flag</p>
      <h1 className="display mt-2 text-5xl">Page not found</h1>
      <p className="mt-3 text-ink-2">That session doesn&apos;t exist (yet).</p>
      <Link href="/" className="mt-6 inline-block rounded-full bg-accent px-5 py-2.5 font-semibold text-white">Back to the season</Link>
    </div>
  );
}
