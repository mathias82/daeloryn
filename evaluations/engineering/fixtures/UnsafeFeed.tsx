// Deliberately unsafe React fixture. NEVER expose to real users.
type Item = { id: string; html: string };
export function UnsafeFeed({ items }: { items: Item[] }) {
  return <ul>{items.map((item, index) =>
    <li key={index}><div dangerouslySetInnerHTML={{ __html: item.html }} /></li>
  )}</ul>;
}
