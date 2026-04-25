import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/QueryProvider";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "NadiNet — NGO Volunteer Coordination Platform",
  description: "Data-driven volunteer coordination platform for NGOs — triangulate community needs, track trust decay, and deploy the right team.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="min-h-screen flex bg-[#0f172a] text-slate-100">
        <QueryProvider>
          <Sidebar />
          <main className="flex-1 min-h-screen overflow-y-auto">
            {children}
          </main>
        </QueryProvider>
      </body>
    </html>
  );
}
