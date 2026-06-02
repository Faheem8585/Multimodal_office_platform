import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { api, apiError } from "@/api/client";
import { Button, Card, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import type { Department, DocumentItem, Page } from "@/lib/types";
import { useAuth } from "@/store/auth";

export default function Documents() {
  const { user, hasRole } = useAuth();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState<Department>(user?.department ?? "hr");
  const [error, setError] = useState<string | null>(null);

  // Deleting a document requires manager+ (enforced again on the backend).
  const canDelete = hasRole("dept_manager");

  const { data, isLoading } = useQuery({
    queryKey: ["documents", department],
    queryFn: async () =>
      (await api.get<Page<DocumentItem>>("/documents", { params: { department, size: 50 } }))
        .data,
    refetchInterval: 5000, // poll so processing -> indexed updates live
  });

  const remove = useMutation({
    mutationFn: async (id: string) => api.delete(`/documents/${id}`),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e) => setError(apiError(e)),
  });

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a file");
      const form = new FormData();
      form.append("file", file);
      form.append("department", department);
      if (title) form.append("title", title);
      return api.post("/documents", form);
    },
    onSuccess: () => {
      setFile(null);
      setTitle("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e) => setError(apiError(e)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    upload.mutate();
  };

  return (
    <div>
      <PageHeader
        title="Documents"
        subtitle="Upload PDFs, Office files, or images — text is extracted (OCR for scans) and indexed for search."
      />

      <Card className="mb-6">
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm sm:col-span-2"
            accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.tiff,.txt,.md,.csv"
          />
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value as Department)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="hr">HR</option>
            <option value="finance">Finance</option>
            <option value="it">IT</option>
          </select>
          <input
            placeholder="Title (optional)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-3"
          />
          <Button type="submit" disabled={upload.isPending || !file}>
            {upload.isPending ? "Uploading…" : "Upload"}
          </Button>
        </form>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </Card>

      {isLoading ? (
        <Spinner />
      ) : (
        <Card>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="pb-2">Title</th>
                <th className="pb-2">Type</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Uploaded</th>
                {canDelete && <th className="pb-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.items.map((doc) => (
                <tr key={doc.id}>
                  <td className="py-3 font-medium text-slate-800">{doc.title}</td>
                  <td className="py-3 text-slate-500">{doc.content_type}</td>
                  <td className="py-3">
                    <StatusBadge status={doc.status} />
                    {doc.error && <span className="ml-2 text-xs text-red-500">{doc.error}</span>}
                  </td>
                  <td className="py-3 text-slate-400">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                  {canDelete && (
                    <td className="py-3 text-right">
                      <button
                        onClick={() => {
                          if (window.confirm(`Delete "${doc.title}"? This can't be undone.`)) {
                            remove.mutate(doc.id);
                          }
                        }}
                        disabled={remove.isPending}
                        className="rounded-lg px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {!data?.items.length && (
                <tr>
                  <td colSpan={canDelete ? 5 : 4} className="py-6 text-center text-slate-400">
                    No documents yet.
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
