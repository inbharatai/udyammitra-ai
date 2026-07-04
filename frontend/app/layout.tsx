import "./globals.css";
import type { Metadata } from "next";
import Logo from "@/components/Logo";

export const metadata: Metadata = {
  title: "UdyamMitra AI — MSME Credit & Cash-flow Intelligence",
  description: "AI credit and cash-flow intelligence for MSMEs. IDBI MSME track prototype.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <header className="no-print border-b border-slate-200 bg-white/90 backdrop-blur sticky top-0 z-20">
          <div className="max-w-7xl mx-auto px-5 py-3 flex items-center gap-3">
            <Logo size={36} />
            <div className="leading-tight">
              <div className="font-bold text-idbi-blue text-lg tracking-tight">UdyamMitra <span className="text-idbi-orange">AI</span></div>
              <div className="text-[11px] text-slate-500 -mt-0.5">MSME Credit &amp; Cash-flow Intelligence</div>
            </div>
            <div className="ml-auto text-xs text-slate-500">IDBI MSME Track · Prototype</div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-5 py-6">{children}</main>
        <footer className="no-print text-center text-xs text-slate-400 py-8">
          UdyamMitra AI · Deterministic scoring + multi-agent explainability · Not a bureau credit score.
        </footer>
      </body>
    </html>
  );
}