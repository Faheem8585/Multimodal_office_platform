"""Load department knowledge bases (HR / Finance / IT) into the running app.

These are generic, sensible-default FAQ/policy documents covering the questions
employees most commonly ask each department. They are written FAQ-style (the
question as a heading, keyword-rich answers) so both keyword and semantic
retrieval surface the right passage. Edit the text to match your real org.

Usage: BASE=http://localhost:8010 python scripts/load_knowledge_base.py
Each department's docs are uploaded by that department's manager account.
"""

# ruff: noqa: E501  -- long lines below are verbatim policy/FAQ prose
import os

import httpx

BASE = os.getenv("BASE", "http://localhost:8010")
API = f"{BASE}/api/v1"

MANAGERS = {
    "hr": ("hr.manager@example.com", "ChangeMe!Mgr123"),
    "finance": ("finance.manager@example.com", "ChangeMe!Mgr123"),
    "it": ("it.manager@example.com", "ChangeMe!Mgr123"),
}

# (department, title, filename, body)
KNOWLEDGE_BASE: list[tuple[str, str, str, str]] = [
    # ----------------------------- HR -----------------------------
    (
        "hr",
        "HR FAQ — Leave & Time Off",
        "hr_leave_faq.txt",
        """Leave and time off — frequently asked questions.

How many vacation days do I get? Full-time employees receive 30 paid annual
leave (vacation) days per calendar year, accrued monthly. Part-time employees
accrue pro-rata.

How do I request leave / book a holiday? Submit a leave request in the platform
under HR > Leave. Choose the type (vacation, sick, parental, unpaid), the start
and end dates, and a short reason. Your department manager approves it. You will
be notified when it is approved or rejected.

How far in advance should I request vacation? At least two weeks for planned
vacation; longer for absences over one week.

Can I carry over unused vacation days? Up to 5 unused days may be carried into
the next year and must be used by 31 March, after which they expire.

What about sick leave? Notify your manager as early as possible on the first day
of illness. A doctor's certificate is required from the fourth consecutive sick
day.

What is the parental leave policy? Eligible employees may take up to 12 months of
parental leave. Contact HR at least 8 weeks before the intended start date.

Who approves my leave? Your direct department manager. Approved vacation days are
deducted from your annual balance automatically.
""",
    ),
    (
        "hr",
        "HR FAQ — Onboarding & First Days",
        "hr_onboarding_faq.txt",
        """Onboarding — what new hires need to know.

What happens on my first day? You will receive a welcome email with your start
time and contact person. HR will help you sign your employment contract, complete
payroll and tax forms, and set up your accounts.

What equipment do I get? IT provisions a laptop and any required peripherals.
Raise an IT ticket if something is missing. Asset assignment is tracked in IT >
Assets.

What is the onboarding checklist? Typical tasks: sign employment contract, submit
payroll/tax and bank details, collect IT equipment, set up email and MFA, complete
security and compliance training within the first week, and meet your team and
onboarding buddy.

Is there a probation period? Yes, the standard probation period is six months,
during which either party may end the contract with shorter notice.

Who is my point of contact? Your manager for day-to-day questions and HR for
contracts, payroll, benefits, and policy questions.
""",
    ),
    (
        "hr",
        "HR FAQ — Payroll, Benefits & Working Hours",
        "hr_payroll_benefits_faq.txt",
        """Payroll, benefits, and working arrangements.

When do I get paid? Salaries are paid monthly on the 25th (or the preceding
business day if the 25th falls on a weekend or holiday).

Where do I find my payslip? Payslips are available from HR each month. Contact HR
if a payslip is missing or looks incorrect.

How do I update my bank details or address? Submit the change to HR; bank detail
changes require verification and apply from the next payroll run.

What benefits are offered? Health insurance, a company pension contribution, paid
sick leave, 30 days annual leave, and learning/development budget. Specific perks
vary by location.

What are the standard working hours? Full-time is 40 hours per week. Flexible
start/finish times are supported around core hours of 10:00–16:00.

What is the remote / hybrid work policy? Hybrid work is supported; coordinate your
in-office days with your team and manager.

How do performance reviews work? Reviews happen twice a year with your manager,
covering goals, feedback, and development.

How do I get a certificate of employment or reference letter? Request it from HR;
allow up to five business days.

What is the notice period if I leave? The standard notice period is defined in
your contract (commonly one to three months). Inform your manager and HR in
writing.
""",
    ),
    # --------------------------- FINANCE ---------------------------
    (
        "finance",
        "Finance FAQ — Expenses & Reimbursements",
        "fin_expenses_faq.txt",
        """Expense reimbursement — frequently asked questions.

How do I submit an expense? Go to Finance > Expenses, create the expense with the
merchant, amount, category, and date, attach the receipt, and submit it.

When do I need approval? Expenses up to 1000 EUR are auto-approved. Expenses above
1000 EUR require approval from your manager and then an administrator before
reimbursement.

Do I need a receipt? Yes. A valid itemised receipt is mandatory for every expense
claim regardless of amount. Photos of paper receipts are accepted.

How long until I'm reimbursed? Approved expenses are reimbursed within 14 days,
paid with your salary or by bank transfer.

What expense categories are there? Travel, accommodation, meals, office supplies,
software, training, and general. Choose the closest category.

Can I claim mileage or per diems? Mileage is reimbursed at the standard rate per
kilometre. Meal per diems apply for overnight business travel.

What cannot be expensed? Personal purchases, fines, alcohol outside client
entertainment, and anything without a receipt.

Who approves my expense? Your department manager for amounts over the threshold,
with a second admin sign-off for large amounts. You are notified on each decision.
""",
    ),
    (
        "finance",
        "Finance FAQ — Business Travel",
        "fin_travel_faq.txt",
        """Business travel policy.

Do I need approval before booking travel? Yes — international travel requires
pre-approval from your manager. Domestic day trips do not.

What can I claim for accommodation? Up to 200 EUR per night for a standard hotel
room. Higher-cost cities may have adjusted limits; ask Finance.

What class of flights can I book? Economy class for flights under six hours;
premium economy may be approved for longer flights with manager sign-off.

How do I book? Book through the approved travel provider where possible, or pay
and claim it back as an expense with receipts.

Are meals covered while travelling? Yes, reasonable meals are covered via per diem
or actuals with receipts, up to the daily limit.

What about visas and travel insurance? Visa fees and company-arranged travel
insurance for business trips are reimbursable.
""",
    ),
    (
        "finance",
        "Finance FAQ — Invoices, Budgets & Procurement",
        "fin_invoices_budgets_faq.txt",
        """Invoices, budgets, purchase orders, and corporate cards.

How do vendors get paid? Vendors submit an invoice quoting a valid purchase order
(PO) number. Standard payment terms are 30 days from a correct invoice.

How do I raise a purchase order or buy something for the company? Submit a purchase
request to Finance/Procurement with the vendor, item, amount, and business
justification. Larger purchases need manager approval.

How do budgets work? Budgets are set per department and fiscal year by category.
You can view allocated vs. spent under Finance > Budgets. Approved expenses are
booked against the matching department budget automatically.

How do I request more budget? Ask your department manager, who raises it with
Finance for the fiscal year.

Do we have corporate cards? Corporate cards may be issued to frequent travellers
and managers. Card transactions must still be reconciled with receipts as
expenses.

What about VAT/tax on expenses? Keep tax-compliant receipts showing VAT; Finance
reclaims VAT where eligible. Cross-border purchases may need extra documentation.

When does the fiscal year run? The fiscal year follows the calendar year unless
stated otherwise for your entity.
""",
    ),
    # ----------------------------- IT ------------------------------
    (
        "it",
        "IT FAQ — Getting Help, Tickets & SLAs",
        "it_support_sla_faq.txt",
        """Getting IT help — tickets and response times.

How do I get IT support? Raise a ticket under IT > Tickets describing the problem,
and set a priority (low, medium, high, critical). You can track status and updates
on the ticket.

What are the response time targets (SLA)? Critical (system down, many users): first
response within 1 hour. High: within 4 business hours. Medium: within 1 business
day. Low: within 3 business days.

What counts as critical? A full outage, security incident, or anything blocking a
whole team from working.

Can I update or close my own ticket? You can add information and close your own
ticket once resolved. IT staff handle assignment and triage.

How do I escalate? Mark the ticket priority appropriately and add a comment; for
true emergencies use the on-call channel.
""",
    ),
    (
        "it",
        "IT FAQ — Accounts, Passwords & MFA",
        "it_accounts_passwords_faq.txt",
        """Accounts, passwords, and multi-factor authentication.

How do I reset my password? Use the self-service password reset on the login page.
If you are locked out, raise an IT ticket or contact the service desk.

I'm locked out of my account — what do I do? Account lockouts usually clear after a
short period; if not, open a ticket and IT will unlock it after verifying your
identity.

How does multi-factor authentication (MFA) work? MFA is required on all company
accounts. Set it up with an authenticator app during onboarding. Lost your second
factor? Raise a ticket to re-enrol.

How do I request access to a system or application? Submit an access request under
IT > Access Requests with the system name, the access level you need (read, write,
admin), and a business justification. Access requests are approved by IT before
being granted.

How is access removed when someone leaves? Offboarding revokes accounts and access
automatically as part of the leaver process.
""",
    ),
    (
        "it",
        "IT FAQ — Remote Access, VPN, Wi-Fi & Devices",
        "it_remote_devices_faq.txt",
        """Remote access, VPN, networking, and hardware.

How do I connect to the VPN? Install the company VPN client (provided on your
laptop) and sign in with your company account and MFA. Raise a ticket if the VPN
keeps disconnecting or won't connect.

How do I access internal systems from home? Connect to the VPN first, then internal
tools are reachable in the browser as usual.

How do I get a new laptop, monitor, or peripheral? Submit an IT ticket describing
what you need. Hardware is assigned and tracked in IT > Assets.

My hardware is broken — what now? Open a ticket; IT will arrange repair or a
replacement and update the asset record.

How do I connect to office Wi-Fi or printers? Use the corporate Wi-Fi network with
your account; printers are added automatically on the corporate network or via a
quick ticket.

What is the policy on personal devices (BYOD)? Personal devices accessing company
data must be enrolled in mobile device management and meet security requirements.
""",
    ),
    (
        "it",
        "IT FAQ — Software, Licenses & Security",
        "it_software_security_faq.txt",
        """Software, licenses, and security.

How do I request new software or a license? Submit an access/software request via
IT with the tool name and business reason. Licensed software needs manager and IT
approval.

Can I install software myself? Standard, approved software can be installed from
the company portal. Anything else needs an IT request for security review.

What do I do about a suspicious or phishing email? Do not click links or open
attachments. Report it using the phishing-report button or raise a security ticket
immediately.

What are the security basics? Use MFA, lock your screen when away, keep your device
encrypted and updated, never share passwords, and store company data only in
approved systems.

I lost my laptop or phone — what now? Report it to IT immediately so the device can
be locked or wiped remotely and credentials rotated.

What is the acceptable use policy? Company devices and accounts are for business
use; limited reasonable personal use is allowed, but no illegal, offensive, or
insecure activity.
""",
    ),
]


def login(client: httpx.Client, email: str, password: str) -> dict[str, str]:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def main() -> None:
    with httpx.Client(timeout=30) as c:
        tokens = {d: login(c, e, p) for d, (e, p) in MANAGERS.items()}
        print(f"Uploading {len(KNOWLEDGE_BASE)} knowledge-base documents...\n")
        for dept, title, fname, body in KNOWLEDGE_BASE:
            r = c.post(
                f"{API}/documents",
                headers=tokens[dept],
                files={"file": (fname, body.encode(), "text/plain")},
                data={"department": dept, "title": title},
            )
            mark = "ok " if r.status_code < 400 else "ERR"
            print(f"  [{mark}] {dept:<7} {title} ({r.status_code})")
            if r.status_code >= 400:
                print(f"        -> {r.text[:200]}")
    print("\nDone. The worker will index these shortly; then the Assistant and")
    print("Search will answer common HR/Finance/IT questions from this content.")


if __name__ == "__main__":
    main()
