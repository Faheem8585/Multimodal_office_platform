import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, apiError } from "@/api/client";
import { Button, Card, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import type { ApprovalRequest } from "@/lib/types";

export default function Approvals() {
  const qc = useQueryClient();
  const [comment, setComment] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: async () =>
      (await api.get<ApprovalRequest[]>("/approvals/requests/pending")).data,
  });

  const decide = useMutation({
    mutationFn: async (vars: { id: string; approve: boolean }) =>
      api.post(`/approvals/requests/${vars.id}/decide`, {
        approve: vars.approve,
        comment: comment[vars.id] || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
      qc.invalidateQueries({ queryKey: ["unread"] });
    },
  });

  if (isLoading) return <Spinner />;

  return (
    <div>
      <PageHeader
        title="Approvals"
        subtitle="Requests awaiting your decision at the current workflow step."
      />

      {decide.isError && <p className="mb-3 text-sm text-red-600">{apiError(decide.error)}</p>}

      <div className="space-y-4">
        {data?.map((req) => {
          const currentStep = req.steps.find((s) => s.order_index === req.current_step);
          return (
            <Card key={req.id}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium text-slate-800">
                    {req.resource_type.replace("_", " ")}
                  </div>
                  <div className="text-xs text-slate-500">
                    {req.department.toUpperCase()} · requested{" "}
                    {new Date(req.created_at).toLocaleDateString()}
                  </div>
                </div>
                <StatusBadge status={req.status} />
              </div>

              <ol className="mt-3 flex flex-wrap gap-2 text-xs">
                {req.steps.map((s) => (
                  <li
                    key={s.order_index}
                    className={`rounded-full px-2.5 py-1 ${
                      s.order_index === req.current_step
                        ? "bg-amber-100 text-amber-800"
                        : s.decision === "approved"
                          ? "bg-green-100 text-green-700"
                          : s.decision === "rejected"
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {s.order_index + 1}. {s.name} ({s.required_role})
                  </li>
                ))}
              </ol>

              {Object.keys(req.context).length > 0 && (
                <pre className="mt-3 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">
                  {JSON.stringify(req.context, null, 2)}
                </pre>
              )}

              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  placeholder={`Comment for "${currentStep?.name}" (optional)`}
                  value={comment[req.id] ?? ""}
                  onChange={(e) => setComment((c) => ({ ...c, [req.id]: e.target.value }))}
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <Button
                  variant="primary"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: req.id, approve: true })}
                >
                  Approve
                </Button>
                <Button
                  variant="danger"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: req.id, approve: false })}
                >
                  Reject
                </Button>
              </div>
            </Card>
          );
        })}
        {!data?.length && (
          <Card>
            <p className="text-sm text-slate-400">Nothing awaiting your approval. 🎉</p>
          </Card>
        )}
      </div>
    </div>
  );
}
