/**
 * Re-created on every navigation, so the `.page-enter` animation replays and
 * each marketing route fades in over the persistent header and footer. See the
 * `.page-enter` note in globals.css for why this is CSS rather than a JS lib.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
