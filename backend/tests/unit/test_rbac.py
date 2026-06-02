from app.models.enums import Department, RoleName
from app.services.rbac import Principal


def member(dept=Department.FINANCE):
    return Principal("u", "e@x.de", dept, frozenset({RoleName.DEPT_MEMBER}))


def manager(dept=Department.FINANCE):
    return Principal("u", "e@x.de", dept, frozenset({RoleName.DEPT_MANAGER}))


def admin():
    return Principal("a", "a@x.de", Department.IT, frozenset({RoleName.ADMIN}))


def test_role_tiers():
    m = member()
    assert m.has_at_least(RoleName.VIEWER)
    assert m.has_at_least(RoleName.DEPT_MEMBER)
    assert not m.has_at_least(RoleName.DEPT_MANAGER)
    assert not m.has_at_least(RoleName.ADMIN)


def test_department_scoping():
    m = member(Department.FINANCE)
    assert m.can_access_department(Department.FINANCE)
    assert not m.can_access_department(Department.HR)


def test_manager_can_manage_own_department_only():
    mgr = manager(Department.HR)
    assert mgr.can_manage_department(Department.HR)
    assert not mgr.can_manage_department(Department.FINANCE)
    # A plain member cannot manage even their own department.
    assert not member(Department.HR).can_manage_department(Department.HR)


def test_admin_is_org_wide():
    a = admin()
    assert a.is_admin
    assert a.can_access_department(Department.HR)
    assert a.can_manage_department(Department.LEGAL)
    assert a.has_at_least(RoleName.ADMIN)


def test_claims_roundtrip():
    mgr = manager(Department.FINANCE)
    claims = mgr.to_claims()
    rebuilt = Principal.from_claims(mgr.user_id, claims)
    assert rebuilt.department == Department.FINANCE
    assert RoleName.DEPT_MANAGER in rebuilt.roles
