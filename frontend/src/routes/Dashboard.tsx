import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { Card, PageHeader, Spinner } from "@/components/ui";
import type { Dashboard as DashboardData } from "@/lib/types";

export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<DashboardData>("/dashboard")).data,
  });

  if (isLoading || !data) return <Spinner />;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={`${data.department.toUpperCase()} workspace · ${data.role_tier}`}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {data.stats.map((stat) => {
          const body = (
            <Card className="h-full transition hover:shadow-md">
              <div className="text-sm text-slate-500">{stat.label}</div>
              <div className="mt-2 text-3xl font-semibold text-slate-900">
                {stat.value}
                {stat.unit && <span className="ml-1 text-lg text-slate-400">{stat.unit}</span>}
              </div>
            </Card>
          );
          return stat.link ? (
            <Link key={stat.key} to={stat.link}>
              {body}
            </Link>
          ) : (
            <div key={stat.key}>{body}</div>
          );
        })}
      </div>

      <h2 className="mb-3 mt-8 text-lg font-semibold text-slate-800">Recent activity</h2>
      <Card>
        {data.recent_activity.length === 0 ? (
          <p className="text-sm text-slate-500">No recent activity.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.recent_activity.map((event) => (
              <li key={event.id} className="flex items-center justify-between py-3 text-sm">
                <span className="text-slate-700">{event.summary}</span>
                <span className="text-xs text-slate-400">
                  {new Date(event.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
