import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { api, apiError } from "@/api/client";
import { Button, Card, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import type { Page } from "@/lib/types";

interface Employee {
  id: string;
  employee_number: string;
  full_name: string;
  work_email: string;
  job_title: string;
  department: string;
  annual_leave_days: number;
}

interface Leave {
  id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: number;
  status: string;
}

type Tab = "employees" | "leave";

export default function HR() {
  const [tab, setTab] = useState<Tab>("employees");

  return (
    <div>
      <PageHeader title="Human Resources" subtitle="Directory, onboarding and leave management." />
      <div className="mb-4 flex gap-2">
        <TabButton active={tab === "employees"} onClick={() => setTab("employees")}>
          Employees
        </TabButton>
        <TabButton active={tab === "leave"} onClick={() => setTab("leave")}>
          Leave
        </TabButton>
      </div>
      {tab === "employees" ? <Employees /> : <LeaveList />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-4 py-2 text-sm font-medium ${
        active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

function Employees() {
  const { data, isLoading } = useQuery({
    queryKey: ["hr", "employees"],
    queryFn: async () => (await api.get<Page<Employee>>("/hr/employees", { params: { size: 50 } })).data,
  });
  if (isLoading) return <Spinner />;
  return (
    <Card>
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-slate-400">
          <tr>
            <th className="pb-2">#</th>
            <th className="pb-2">Name</th>
            <th className="pb-2">Title</th>
            <th className="pb-2">Dept</th>
            <th className="pb-2">Leave days</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data?.items.map((e) => (
            <tr key={e.id}>
              <td className="py-3 text-slate-400">{e.employee_number}</td>
              <td className="py-3 font-medium text-slate-800">{e.full_name}</td>
              <td className="py-3 text-slate-500">{e.job_title}</td>
              <td className="py-3 uppercase text-slate-500">{e.department}</td>
              <td className="py-3">{e.annual_leave_days}</td>
            </tr>
          ))}
          {!data?.items.length && (
            <tr>
              <td colSpan={5} className="py-6 text-center text-slate-400">
                No employees yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Card>
  );
}

function RequestLeaveForm() {
  const qc = useQueryClient();
  const [employeeId, setEmployeeId] = useState("");
  const [leaveType, setLeaveType] = useState("vacation");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: employees } = useQuery({
    queryKey: ["hr", "employees"],
    queryFn: async () =>
      (await api.get<Page<Employee>>("/hr/employees", { params: { size: 100 } })).data,
  });

  const submitLeave = useMutation({
    mutationFn: async () =>
      api.post("/hr/leave", {
        employee_id: employeeId,
        leave_type: leaveType,
        start_date: start,
        end_date: end,
        reason,
      }),
    onSuccess: () => {
      setError(null);
      setReason("");
      // Refresh the leave list AND the dashboard (pending-leave card + activity)
      // and the notification badge so the new request shows up immediately.
      qc.invalidateQueries({ queryKey: ["hr", "leave"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["unread"] });
    },
    onError: (e) => setError(apiError(e)),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (employeeId && start && end) submitLeave.mutate();
  };

  return (
    <Card className="mb-6">
      <h2 className="mb-3 font-medium text-slate-800">Request leave</h2>
      <form onSubmit={onSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-5">
        <select
          value={employeeId}
          onChange={(e) => setEmployeeId(e.target.value)}
          required
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-2"
        >
          <option value="">Select employee…</option>
          {employees?.items.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.full_name} ({emp.department.toUpperCase()})
            </option>
          ))}
        </select>
        <select
          value={leaveType}
          onChange={(e) => setLeaveType(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="vacation">Vacation</option>
          <option value="sick">Sick</option>
          <option value="parental">Parental</option>
          <option value="unpaid">Unpaid</option>
        </select>
        <input
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          required
          aria-label="Start date"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          type="date"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          required
          aria-label="End date"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          placeholder="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-4"
        />
        <Button type="submit" disabled={submitLeave.isPending}>
          {submitLeave.isPending ? "Submitting…" : "Submit request"}
        </Button>
      </form>
      <p className="mt-2 text-xs text-slate-400">
        The request goes to the employee's department manager for approval and appears on the
        dashboard and Approvals queue.
      </p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {submitLeave.isSuccess && (
        <p className="mt-2 text-sm text-green-600">Leave request submitted for approval.</p>
      )}
    </Card>
  );
}

function LeaveList() {
  const { data, isLoading } = useQuery({
    queryKey: ["hr", "leave"],
    queryFn: async () => (await api.get<Page<Leave>>("/hr/leave", { params: { size: 50 } })).data,
  });
  return (
    <>
      <RequestLeaveForm />
      {isLoading ? (
        <Spinner />
      ) : (
        <Card>
          <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-slate-400">
          <tr>
            <th className="pb-2">Type</th>
            <th className="pb-2">From</th>
            <th className="pb-2">To</th>
            <th className="pb-2">Days</th>
            <th className="pb-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data?.items.map((l) => (
            <tr key={l.id}>
              <td className="py-3 capitalize text-slate-700">{l.leave_type}</td>
              <td className="py-3 text-slate-500">{l.start_date}</td>
              <td className="py-3 text-slate-500">{l.end_date}</td>
              <td className="py-3">{l.days}</td>
              <td className="py-3">
                <StatusBadge status={l.status} />
              </td>
            </tr>
          ))}
          {!data?.items.length && (
            <tr>
              <td colSpan={5} className="py-6 text-center text-slate-400">
                No leave requests.
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
