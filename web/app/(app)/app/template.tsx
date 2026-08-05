/**
 * Re-created on every navigation, so the `.page-enter` animation replays and the
 * dashboard content fades in while the nav, top bar, and tab bar stay put. See
 * the `.page-enter` note in globals.css.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
