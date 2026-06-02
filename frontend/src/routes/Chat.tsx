import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { api, apiError } from "@/api/client";
import { Button, Card, PageHeader } from "@/components/ui";
import type { ChatResponse, Department } from "@/lib/types";
import { useAuth } from "@/store/auth";

interface Turn {
  question: string;
  response?: ChatResponse;
  error?: string;
}

export default function Chat() {
  const { user } = useAuth();
  const [department, setDepartment] = useState<Department>(user?.department ?? "hr");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  const ask = useMutation({
    mutationFn: async (q: string) =>
      (await api.post<ChatResponse>("/chat", { question: q, department, top_k: 6 })).data,
    onSuccess: (response, q) =>
      setTurns((t) => t.map((turn) => (turn.question === q && !turn.response ? { ...turn, response } : turn))),
    onError: (err, q) =>
      setTurns((t) =>
        t.map((turn) => (turn.question === q && !turn.response ? { ...turn, error: apiError(err) } : turn)),
      ),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setTurns((t) => [...t, { question }]);
    ask.mutate(question);
    setQuestion("");
  };

  return (
    <div>
      <PageHeader
        title="Department assistant"
        subtitle="Ask questions grounded in your department's documents (RAG). Answers cite their sources."
      />

      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm text-slate-500">Knowledge base:</span>
        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value as Department)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
        >
          <option value="hr">HR</option>
          <option value="finance">Finance</option>
          <option value="it">IT</option>
        </select>
      </div>

      <div className="space-y-4">
        {turns.map((turn, i) => (
          <div key={i} className="space-y-2">
            <div className="rounded-lg bg-brand-50 px-4 py-2 text-sm font-medium text-brand-800">
              {turn.question}
            </div>
            {turn.response ? (
              <Card>
                <p className="whitespace-pre-wrap text-sm text-slate-700">{turn.response.answer}</p>
                {turn.response.sources.length > 0 && (
                  <div className="mt-3 border-t border-slate-100 pt-3">
                    <p className="mb-1 text-xs font-medium uppercase text-slate-400">Sources</p>
                    {turn.response.sources.map((s, j) => (
                      <p key={j} className="truncate text-xs text-slate-500">
                        • {s.content.slice(0, 120)}
                      </p>
                    ))}
                  </div>
                )}
              </Card>
            ) : turn.error ? (
              <p className="text-sm text-red-600">{turn.error}</p>
            ) : (
              <p className="text-sm text-slate-400">Thinking…</p>
            )}
          </div>
        ))}
      </div>

      <form onSubmit={submit} className="mt-6 flex gap-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question…"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <Button type="submit" disabled={ask.isPending}>
          Ask
        </Button>
      </form>
    </div>
  );
}
