import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { api, apiError } from "@/api/client";
import { Button, Card, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import type { Page } from "@/lib/types";

interface Ticket {
  id: string;
  title: string;
  status: string;
  priority: string;
  requester_department: string;
  created_at: string;
}

interface AccessRequest {
  id: string;
  system: string;
  access_level: string;
  status: string;
}

type Tab = "tickets" | "access";

export default function IT() {
  const [tab, setTab] = useState<Tab>("tickets");
  return (
    <div>
      <PageHeader title="IT" subtitle="Ticketing, asset inventory and access requests." />
      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setTab("tickets")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === "tickets" ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-700"}`}
        >
          Tickets
        </button>
        <button
          onClick={() => setTab("access")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === "access" ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-700"}`}
        >
          Access requests
        </button>
      </div>
      {tab === "tickets" ? <Tickets /> : <AccessRequests />}
    </div>
  );
}

function Tickets() {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("medium");

  const { data, isLoading } = useQuery({
    queryKey: ["it", "tickets"],
    queryFn: async () => (await api.get<Page<Ticket>>("/it/tickets", { params: { size: 50 } })).data,
  });

  const create = useMutation({
    mutationFn: async () => api.post("/it/tickets", { title, priority, description: "" }),
    onSuccess: () => {
      setTitle("");
      qc.invalidateQueries({ queryKey: ["it", "tickets"] });
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (title) create.mutate();
  };

  return (
    <>
      <Card className="mb-6">
        <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input
            placeholder="Describe your issue"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-2"
          />
          <div className="flex gap-2">
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <Button type="submit" disabled={create.isPending}>
              Raise
            </Button>
          </div>
        </form>
        {create.isError && <p className="mt-2 text-sm text-red-600">{apiError(create.error)}</p>}
      </Card>

      {isLoading ? (
        <Spinner />
      ) : (
        <Card>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="pb-2">Title</th>
                <th className="pb-2">Priority</th>
                <th className="pb-2">From</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.items.map((t) => (
                <tr key={t.id}>
                  <td className="py-3 font-medium text-slate-800">{t.title}</td>
                  <td className="py-3 capitalize text-slate-500">{t.priority}</td>
                  <td className="py-3 uppercase text-slate-400">{t.requester_department}</td>
                  <td className="py-3">
                    <StatusBadge status={t.status} />
                  </td>
                </tr>
              ))}
              {!data?.items.length && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-slate-400">
                    No tickets.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}

function AccessRequests() {
  const qc = useQueryClient();
  const [system, setSystem] = useState("");
  const [level, setLevel] = useState("read");

  const { data, isLoading } = useQuery({
    queryKey: ["it", "access"],
    queryFn: async () =>
      (await api.get<Page<AccessRequest>>("/it/access-requests", { params: { size: 50 } })).data,
  });

  const create = useMutation({
    mutationFn: async () =>
      api.post("/it/access-requests", { system, access_level: level, justification: "" }),
    onSuccess: () => {
      setSystem("");
      qc.invalidateQueries({ queryKey: ["it", "access"] });
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (system) create.mutate();
  };

  return (
    <>
      <Card className="mb-6">
        <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input
            placeholder="System (e.g. VPN, GitHub)"
            value={system}
            onChange={(e) => setSystem(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="read">Read</option>
            <option value="write">Write</option>
            <option value="admin">Admin</option>
          </select>
          <Button type="submit" disabled={create.isPending}>
            Request access
          </Button>
        </form>
      </Card>

      {isLoading ? (
        <Spinner />
      ) : (
        <Card>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="pb-2">System</th>
                <th className="pb-2">Level</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.items.map((a) => (
                <tr key={a.id}>
                  <td className="py-3 font-medium text-slate-800">{a.system}</td>
                  <td className="py-3 capitalize text-slate-500">{a.access_level}</td>
                  <td className="py-3">
                    <StatusBadge status={a.status} />
                  </td>
                </tr>
              ))}
              {!data?.items.length && (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-slate-400">
                    No access requests.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
