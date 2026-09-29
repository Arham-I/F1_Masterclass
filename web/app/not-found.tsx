import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-24">
      <h1 className="wide text-4xl">Red flag: page not found</h1>
      <p className="mt-3 text-ink-2">There&apos;s no page at this address. Pick a weekend from the calendar instead.</p>
      <Link href="/" className="mt-6 inline-block rounded-md bg-accent px-5 py-2.5 font-semibold text-white">Go to the calendar</Link>
    </div>
  );
}
