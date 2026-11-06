/** Re-mounts on every navigation inside the app, so each page fades and slides in. */
export default function AppTemplate({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
