import { redirect } from "next/navigation";

// /docs has no content of its own   it sends readers straight into the first
// page worth reading rather than an index they have to click through.
export default function DocsIndexPage() {
  redirect("/docs/getting-started");
}
