"use client";

import { useEffect, useId, useRef, useState } from "react";

/** A small "?" that explains a term in plain words. Opens on hover or keyboard focus; a click or
 *  tap pins it open (phones), and Escape or a click elsewhere closes it. */
export default function InfoTip({ label, children, align = "left" }: {
  label: string; children: React.ReactNode; align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);     // opened by click/tap: stays until dismissed
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = () => { setOpen(false); setPinned(false); };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    const onClick = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && close();
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onClick); };
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex align-middle normal-case not-italic tracking-normal"
      onMouseEnter={() => setOpen(true)} onMouseLeave={() => !pinned && setOpen(false)}>
      <button
        type="button"
        aria-label={`What is ${label}?`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => { setPinned(!pinned || !open); setOpen(!pinned || !open); }}
        onFocus={() => setOpen(true)}
        onBlur={() => !pinned && setOpen(false)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-ink-3 text-[10px] font-bold leading-none text-ink-2 hover:border-ink hover:text-ink"
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className={`absolute top-6 z-30 w-64 rounded border border-line bg-surface-3 p-3 text-left font-sans text-[13px] font-normal leading-snug text-ink-2 shadow-2xl ${align === "right" ? "right-0" : "left-0"}`}
        >
          <b className="mb-1 block text-ink">{label}</b>
          {children}
        </span>
      )}
    </span>
  );
}
