import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { api, apiError } from "@/api/client";
import { Button, Card, PageHeader } from "@/components/ui";
import type { Department, SearchHit } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [department, setDepartment] = useState<Department | "">("");

  const search = useMutation({
    mutationFn: async () =>
      (
        await api.post<{ hits: SearchHit[] }>("/search/semantic", {
          query,
          department: department || null,
          limit: 10,
        })
      ).data.hits,
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) search.mutate();
  };

  return (
    <div>
      <PageHeader
        title="Semantic search"
        subtitle="Search across documents your role can access — by meaning, not just keywords."
      />

      <Card className="mb-6">
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. parental leave policy"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value as Department | "")}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">All my departments</option>
            <option value="hr">HR</option>
            <option value="finance">Finance</option>
            <option value="it">IT</option>
          </select>
          <Button type="submit" disabled={search.isPending}>
            {search.isPending ? "Searching…" : "Search"}
          </Button>
        </form>
      </Card>

      {search.isError && <p className="text-sm text-red-600">{apiError(search.error)}</p>}

      <div className="space-y-3">
        {search.data?.map((hit) => (
          <Card key={hit.chunk_id}>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs text-slate-400">Doc {hit.document_id.slice(0, 8)}</span>
              <span className="text-xs font-medium text-brand-600">
                {(hit.score * 100).toFixed(0)}% match
              </span>
            </div>
            <p className="text-sm text-slate-700">{hit.content}</p>
          </Card>
        ))}
        {search.data?.length === 0 && (
          <p className="text-sm text-slate-400">No matches found.</p>
        )}
      </div>
    </div>
  );
}
