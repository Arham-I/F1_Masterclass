import type { Driver } from "@/lib/types";

/** Driver identity: team-colour stripe + three-letter code (+ optional name). Colour is never the
 *  only cue - the code is always shown. */
export default function DriverTag({ code, d, showName = false, className = "" }: {
  code: string; d?: Driver; showName?: boolean; className?: string;
}) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-2 ${className}`}>
      <span aria-hidden className="h-4 w-1 shrink-0 rounded-full" style={{ background: d?.color ?? "#8a8d93" }} />
      <span className="wide text-[13px]">{code}</span>
      {showName && d && <span className="hidden truncate text-[13px] text-ink-2 sm:inline">{d.name}</span>}
    </span>
  );
}
