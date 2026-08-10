/**
 * Re-created on every navigation, so the `.page-enter` animation replays and each
 * auth card fades in within the shared shell. See the `.page-enter` note in
 * globals.css.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
