"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Dashboard",     icon: "⬡" },
  { href: "/signals",   label: "Need signals",  icon: "📡" },
  { href: "/decay",     label: "Trust decay",   icon: "⏳" },
  { href: "/kinship",   label: "Kinship graph", icon: "🕸" },
  { href: "/log",       label: "Signal log",    icon: "📋" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 flex flex-col bg-[#0b1120] border-r border-slate-800">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-teal-400 to-indigo-500 flex items-center justify-center text-white font-bold text-sm shadow-lg">
            N
          </div>
          <div>
            <p className="font-bold text-white text-sm leading-none">NadiNet</p>
            <p className="text-xs text-slate-500 mt-0.5">Coordinator</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
                ${active
                  ? "bg-teal-500/10 text-teal-400 border border-teal-500/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }
              `}
            >
              <span className="text-base leading-none">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-slate-800">
        <p className="text-xs text-slate-600">NadiNet v1.0 · UTC</p>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
          <span className="text-xs text-slate-500">All systems online</span>
        </div>
      </div>
    </aside>
  );
}
