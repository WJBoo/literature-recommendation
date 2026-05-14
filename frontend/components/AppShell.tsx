import {
  BookOpen,
  BookmarkCheck,
  Mail,
  PenLine,
  Music2,
  Search,
  UserRound,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { AccountTopNav } from "./AccountTopNav";

const navItems = [
  { href: "/", label: "Discover", icon: BookOpen },
  { href: "/continue-reading", label: "Continue Reading", icon: BookmarkCheck },
  { href: "/search", label: "Search", icon: Search },
  { href: "/music", label: "Music", icon: Music2 },
  { href: "/profile", label: "Profile", icon: UserRound },
  { href: "/connect", label: "Writers", icon: UsersRound },
  { href: "/messages", label: "Messages", icon: Mail },
  { href: "/post", label: "Post", icon: PenLine },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/">
          Linguaphilia
        </Link>
        <nav className="nav-list" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link className="nav-link" href={item.href} key={item.href}>
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="main">
        <div className="app-account-bar" aria-label="Account controls">
          <AccountTopNav />
        </div>
        {children}
      </main>
    </div>
  );
}
