import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { Badge } from "@/components/ui";
import type { Department } from "@/lib/types";
import { useAuth } from "@/store/auth";

interface NavItem {
  to: string;
  label: string;
  show: boolean;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const { data: unread } = useQuery({
    queryKey: ["unread"],
    queryFn: async () =>
      (await api.get<{ unread: number }>("/notifications/unread-count")).data.unread,
    refetchInterval: 30000,
  });

  const dept = user?.department;
  const isAdmin = user?.roles.includes("admin") ?? false;
  const seesDept = (d: Department) => isAdmin || dept === d;

  const items: NavItem[] = [
    { to: "/", label: "Dashboard", show: true },
    { to: "/documents", label: "Documents", show: true },
    { to: "/search", label: "Search", show: true },
    { to: "/chat", label: "Assistant", show: true },
    { to: "/approvals", label: "Approvals", show: true },
    { to: "/hr", label: "HR", show: seesDept("hr") },
    { to: "/finance", label: "Finance", show: seesDept("finance") },
    { to: "/it", label: "IT", show: seesDept("it") },
  ];

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside
        className={`${open ? "block" : "hidden"} fixed inset-y-0 z-20 w-60 border-r border-slate-200 bg-white md:static md:block`}
      >
        <div className="flex h-16 items-center px-5 text-lg font-semibold text-brand-700">
          Office&nbsp;Platform
        </div>
        <nav className="space-y-1 px-3">
          {items
            .filter((i) => i.show)
            .map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium ${
                    isActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-slate-600 hover:bg-slate-100"
                  }`
                }
              >
                <span>{item.label}</span>
                {item.to === "/approvals" && !!unread && unread > 0 && (
                  <Badge tone="amber">{unread}</Badge>
                )}
              </NavLink>
            ))}
        </nav>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4">
          <button
            className="rounded p-2 text-slate-500 hover:bg-slate-100 md:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            ☰
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-3 text-sm">
            <div className="text-right">
              <div className="font-medium text-slate-800">{user?.full_name}</div>
              <div className="text-xs text-slate-500">
                {user?.department?.toUpperCase()} · {user?.roles.join(", ")}
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium hover:bg-slate-200"
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
