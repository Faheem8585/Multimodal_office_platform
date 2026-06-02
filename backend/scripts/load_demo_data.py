"""Populate the running local instance with demo data via the HTTP API.

Usage: BASE=http://localhost:8010 python scripts/load_demo_data.py
Assumes the app is running and `python -m app.initial_data` has been run
(seeded users + default approval workflows).
"""

# ruff: noqa: E501  -- long lines below are verbatim demo document prose
import os

import httpx

BASE = os.getenv("BASE", "http://localhost:8010")
API = f"{BASE}/api/v1"

USERS = {
    "admin": ("admin@example.com", "ChangeMe!Admin123"),
    "fin_mgr": ("finance.manager@example.com", "ChangeMe!Mgr123"),
    "fin_mem": ("finance.member@example.com", "ChangeMe!Mem123"),
    "hr_mgr": ("hr.manager@example.com", "ChangeMe!Mgr123"),
    "it_mgr": ("it.manager@example.com", "ChangeMe!Mgr123"),
}


def login(client: httpx.Client, email: str, password: str) -> dict[str, str]:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def show(label: str, r: httpx.Response) -> dict:
    ok = r.status_code < 400
    mark = "ok " if ok else "ERR"
    print(f"  [{mark}] {label}: {r.status_code}")
    if not ok:
        print(f"        -> {r.text[:200]}")
    return r.json() if ok and r.content else {}


def main() -> None:
    with httpx.Client(timeout=30) as c:
        tok = {k: login(c, e, p) for k, (e, p) in USERS.items()}
        print("logged in:", ", ".join(tok))

        # --- Finance: budget + expenses (one auto-approved, one needs approval) ---
        print("\nFinance:")
        show(
            "budget FY2026",
            c.post(
                f"{API}/finance/budgets",
                headers=tok["fin_mgr"],
                json={
                    "department": "finance",
                    "fiscal_year": 2026,
                    "category": "general",
                    "allocated": 50000,
                    "currency": "EUR",
                },
            ),
        )
        for merchant, amount in [
            ("Office Cafe", 42.50),
            ("Team offsite lunch", 180.00),
            ("Standing desks (bulk)", 2500.00),
            ("Conference tickets", 3200.00),
        ]:
            exp = show(
                f"expense {merchant} €{amount}",
                c.post(
                    f"{API}/finance/expenses",
                    headers=tok["fin_mem"],
                    json={
                        "merchant": merchant,
                        "amount": amount,
                        "category": "general",
                        "description": f"{merchant} purchase",
                    },
                ),
            )
            if exp.get("id"):
                show(
                    f"  submit {merchant}",
                    c.post(f"{API}/finance/expenses/{exp['id']}/submit", headers=tok["fin_mem"]),
                )
        show(
            "invoice ACME",
            c.post(
                f"{API}/finance/invoices",
                headers=tok["fin_mgr"],
                json={
                    "invoice_number": "INV-2026-001",
                    "vendor_name": "ACME Supplies",
                    "amount": 1240.00,
                    "currency": "EUR",
                    "due_date": "2026-07-15",
                },
            ),
        )

        # --- HR: employees, onboarding, leave (pending approval) ---
        print("\nHR:")
        emps = []
        for num, name, email, title, dept in [
            ("EMP-1001", "Alice Schmidt", "alice.schmidt@example.com", "Recruiter", "hr"),
            ("EMP-1002", "Bob Müller", "bob.mueller@example.com", "Accountant", "finance"),
            ("EMP-1003", "Carla Rossi", "carla.rossi@example.com", "Sysadmin", "it"),
        ]:
            e = show(
                f"employee {name}",
                c.post(
                    f"{API}/hr/employees",
                    headers=tok["hr_mgr"],
                    json={
                        "employee_number": num,
                        "full_name": name,
                        "work_email": email,
                        "job_title": title,
                        "department": dept,
                        "annual_leave_days": 30,
                    },
                ),
            )
            if e.get("id"):
                emps.append(e["id"])
        if emps:
            show(
                "onboarding task",
                c.post(
                    f"{API}/hr/employees/{emps[0]}/onboarding",
                    headers=tok["hr_mgr"],
                    json={"title": "Sign employment contract", "description": "HR vault upload"},
                ),
            )
            show(
                "leave request (pending approval)",
                c.post(
                    f"{API}/hr/leave",
                    headers=tok["hr_mgr"],
                    json={
                        "employee_id": emps[0],
                        "leave_type": "vacation",
                        "start_date": "2026-08-10",
                        "end_date": "2026-08-14",
                        "reason": "Summer holiday",
                    },
                ),
            )

        # --- IT: assets, tickets, access request (pending approval) ---
        print("\nIT:")
        for tag, name, cat in [
            ("IT-LAP-001", "MacBook Pro 16", "laptop"),
            ("IT-MON-001", 'Dell 27" Monitor', "monitor"),
        ]:
            show(
                f"asset {tag}",
                c.post(
                    f"{API}/it/assets",
                    headers=tok["it_mgr"],
                    json={
                        "asset_tag": tag,
                        "name": name,
                        "category": cat,
                    },
                ),
            )
        show(
            "ticket (finance user)",
            c.post(
                f"{API}/it/tickets",
                headers=tok["fin_mem"],
                json={
                    "title": "VPN keeps disconnecting",
                    "description": "Drops every ~10 min",
                    "priority": "high",
                },
            ),
        )
        show(
            "ticket (hr user)",
            c.post(
                f"{API}/it/tickets",
                headers=tok["hr_mgr"],
                json={
                    "title": "Need a second monitor",
                    "priority": "low",
                },
            ),
        )
        show(
            "access request (pending approval)",
            c.post(
                f"{API}/it/access-requests",
                headers=tok["fin_mem"],
                json={
                    "system": "Financial Reporting DB",
                    "access_level": "read",
                    "justification": "Quarterly close reporting",
                },
            ),
        )

        # --- Documents: upload some text so search + assistant have content ---
        print("\nDocuments (will be indexed by the worker):")
        docs = [
            (
                "hr",
                "Leave Policy",
                "leave_policy.txt",
                "Annual leave policy: full-time employees accrue 30 paid vacation days per year. "
                "Parental leave is up to 12 months. Sick leave requires a doctor's note after 3 days. "
                "Requests must be approved by the employee's department manager.",
            ),
            (
                "hr",
                "Onboarding Checklist",
                "onboarding.txt",
                "New hire onboarding: sign employment contract, set up payroll and tax forms, "
                "collect IT equipment, complete security training within the first week.",
            ),
            (
                "finance",
                "Expense Reimbursement Policy",
                "expense_policy.txt",
                "Expenses up to 1000 EUR are auto-approved. Expenses above 1000 EUR require manager "
                "and admin sign-off. Receipts are mandatory. Reimbursements are paid within 14 days.",
            ),
            (
                "finance",
                "Travel Policy",
                "travel_policy.txt",
                "Employees may claim up to 200 EUR per night for accommodation and economy class flights. "
                "Pre-approval is required for international travel.",
            ),
        ]
        for dept, title, fname, text in docs:
            tk = tok["hr_mgr"] if dept == "hr" else tok["fin_mgr"]
            show(
                f"upload {title}",
                c.post(
                    f"{API}/documents",
                    headers=tk,
                    files={"file": (fname, text.encode(), "text/plain")},
                    data={"department": dept, "title": title},
                ),
            )

    print("\nDone. Refresh the app — dashboards, lists, and approvals are now populated.")
    print("Tip: log in as finance.manager@example.com then admin@example.com to approve the")
    print("large expenses on the Approvals page (the >1000 EUR ones are pending).")


if __name__ == "__main__":
    main()
