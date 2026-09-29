/** Fixed-height rows placed by index with a CSS transform, so when the order changes (a new
 *  session is revealed) each row slides to its new place instead of the list jumping. */
export default function Glide<T>({ items, keyOf, rowHeight, render, label }: {
  items: T[]; keyOf: (t: T) => string; rowHeight: number; render: (t: T, i: number) => React.ReactNode; label?: string;
}) {
  // Render in a stable (alphabetical) DOM order so React keeps each element and CSS can animate it.
  const placed = items.map((t, i) => ({ t, i, k: keyOf(t) })).sort((a, b) => a.k.localeCompare(b.k));
  return (
    <div role="list" aria-label={label} className="relative" style={{ height: items.length * rowHeight }}>
      {placed.map(({ t, i, k }) => (
        <div
          key={k}
          role="listitem"
          aria-posinset={i + 1}
          aria-setsize={items.length}
          className="glide absolute inset-x-0 top-0"
          style={{ transform: `translateY(${i * rowHeight}px)`, height: rowHeight }}
        >
          {render(t, i)}
        </div>
      ))}
    </div>
  );
}
