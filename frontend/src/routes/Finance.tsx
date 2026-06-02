import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { api, apiError } from "@/api/client";
import { Button, Card, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import type { Page } from "@/lib/types";

interface Expense {
  id: string;
  merchant: string;
  category: string;
  amount: string;
  currency: string;
  status: string;
  created_at: string;
}

async function downloadReport(path: string, filename: string) {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Finance() {
  const qc = useQueryClient();
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["finance", "expenses"],
    queryFn: async () =>
      (await api.get<Page<Expense>>("/finance/expenses", { params: { size: 50 } })).data,
  });

  const create = useMutation({
    mutationFn: async () => {
      const res = await api.post<Expense>("/finance/expenses", {
        merchant,
        amount: Number(amount),
        category: "general",
      });
      // Immediately submit for approval (auto-approves if under threshold).
      await api.post(`/finance/expenses/${res.data.id}/submit`);
    },
    onSuccess: () => {
      setMerchant("");
      setAmount("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["finance", "expenses"] });
    },
    onError: (e) => setError(apiError(e)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (merchant && amount) create.mutate();
  };

  return (
    <div>
      <PageHeader title="Finance" subtitle="Expense submission, approvals and budget tracking." />

      <Card className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-medium text-slate-800">Submit an expense</h2>
          <Button
            variant="secondary"
            onClick={() => downloadReport("/reports/expenses.xlsx", "expenses.xlsx")}
          >
            Export XLSX
          </Button>
        </div>
        <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input
            placeholder="Merchant"
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            placeholder="Amount (EUR)"
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Submitting…" : "Submit expense"}
          </Button>
        </form>
        <p className="mt-2 text-xs text-slate-400">
          Expenses over the configured threshold (default €1000) route to manager approval;
          smaller ones are auto-approved.
        </p>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </Card>

      {isLoading ? (
        <Spinner />
      ) : (
        <Card>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="pb-2">Merchant</th>
                <th className="pb-2">Category</th>
                <th className="pb-2">Amount</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.items.map((x) => (
                <tr key={x.id}>
                  <td className="py-3 font-medium text-slate-800">{x.merchant || "—"}</td>
                  <td className="py-3 text-slate-500">{x.category}</td>
                  <td className="py-3">
                    {x.amount} {x.currency}
                  </td>
                  <td className="py-3">
                    <StatusBadge status={x.status} />
                  </td>
                </tr>
              ))}
              {!data?.items.length && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-slate-400">
                    No expenses yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
