"use client";

import { useEffect, useId, useRef, useState } from "react";

/** A small "?" button that explains a term in plain words. Opens on click/tap (works on phones),
 *  closes on Escape or a click elsewhere. */
export default function InfoTip({ label, children, align = "left" }: {
  label: string; children: React.ReactNode; align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onClick = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onClick); };
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex align-middle normal-case not-italic tracking-normal">
      <button
        type="button"
        aria-label={`What is ${label}?`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-ink-3 text-[10px] font-bold leading-none text-ink-2 hover:border-ink hover:text-ink"
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className={`rise absolute top-6 z-30 w-64 rounded-lg border border-line bg-surface-3 p-3 text-left font-sans text-[13px] font-normal leading-snug text-ink-2 shadow-2xl ${align === "right" ? "right-0" : "left-0"}`}
        >
          <b className="mb-1 block text-ink">{label}</b>
          {children}
        </span>
      )}
    </span>
  );
}
