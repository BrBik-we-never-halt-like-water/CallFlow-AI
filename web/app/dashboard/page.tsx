import Dashboard from "../ui/dashboard";
import { SiteHeader } from "../ui/site";

export const metadata = {
  title: "Dashboard — CallFlow AI",
};

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-white">
      <SiteHeader cta={false} />
      <Dashboard />
    </div>
  );
}
