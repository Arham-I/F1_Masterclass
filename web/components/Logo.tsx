/** Mark: the start-light gantry as an LED matrix - a chamfered housing with two rows of five
 *  lamps, the first three lit (a weekend in progress). Drawn on whole pixels so it stays crisp. */
export default function Logo({ size = 22 }: { size?: number }) {
  const lit = "var(--led-on)", off = "var(--led-off)";
  return (
    <svg width={(size * 30) / 18} height={size} viewBox="0 0 30 18" aria-hidden shapeRendering="crispEdges">
      <path d="M0 0 H26 L30 4 V18 H0 Z" fill="var(--housing)" />
      {[0, 1, 2, 3, 4].flatMap((c) => [0, 1].map((r) => (
        <rect key={`${c}${r}`} x={3 + c * 5} y={4 + r * 6} width={4} height={4} fill={c < 3 ? lit : off} />
      )))}
    </svg>
  );
}
