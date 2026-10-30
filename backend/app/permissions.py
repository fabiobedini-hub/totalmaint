"""Who may do what, inside a group.

Every member can SEE everything in their group and gets reminders. What they may CHANGE
comes from their role. Roles are per group: the four built-in ones are created with every
group, the group admin can tick permissions on and off and add roles of their own.
Owner is locked: it always has every permission, so nobody can lock the group out.

All checks go through `require(...)` / `Ctx.can(...)` – the frontend only hides buttons,
the server is what actually says no.
"""
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .auth import current_user
from .db import get_db
from .lang import INDEX, default_group_name, norm, pick

# key -> (English, Norwegian, Italian). The order is the order in the role editor.
PERMISSIONS: dict[str, tuple[str, str, str]] = {
    "assets.create": ("Create things", "Opprette ting", "Creare oggetti"),
    "assets.edit": ("Edit things", "Endre ting", "Modificare oggetti"),
    "assets.delete": ("Delete things", "Slette ting", "Eliminare oggetti"),
    "components.create": ("Create components", "Opprette komponenter", "Creare componenti"),
    "components.edit": ("Edit components", "Endre komponenter", "Modificare componenti"),
    "components.delete": ("Delete components", "Slette komponenter", "Eliminare componenti"),
    "tasks.create": ("Create tasks", "Opprette oppgaver", "Creare attività"),
    "tasks.edit": ("Edit tasks", "Endre oppgaver", "Modificare attività"),
    "tasks.delete": ("Delete tasks", "Slette oppgaver", "Eliminare attività"),
    "tasks.complete": ("Mark tasks as done", "Markere oppgaver som utført", "Segnare attività come fatte"),
    "history.delete": ("Delete history and purchases", "Slette historikk og kjøp", "Eliminare storico e acquisti"),
    "counters.record": ("Record km / hours", "Registrere km / timer", "Registrare km / ore"),
    "parts.manage": ("Spare parts and shopping list", "Reservedeler og handleliste", "Ricambi e lista della spesa"),
    "warranties.manage": ("Warranties", "Garantier", "Garanzie"),
    "vendors.manage": ("Vendors", "Leverandører", "Fornitori"),
    "attachments.add": ("Add files", "Legge til filer", "Aggiungere file"),
    "attachments.delete": ("Delete files", "Slette filer", "Eliminare file"),
    "templates.apply": ("Use templates", "Bruke maler", "Usare modelli"),
    "members.manage": ("Invite and manage members", "Invitere og administrere medlemmer", "Invitare e gestire membri"),
    "roles.manage": ("Edit roles", "Endre roller", "Modificare ruoli"),
}
ALL = list(PERMISSIONS)

BUILTIN_ROLES: list[tuple[str, tuple[str, str, str], list[str]]] = [
    ("owner", ("Owner", "Eier", "Proprietario"), ALL),
    ("admin", ("Admin", "Administrator", "Amministratore"), ALL),
    ("creator", ("Creator", "Bidragsyter", "Collaboratore"), [
        "components.create", "components.edit", "tasks.create", "tasks.edit", "tasks.complete",
        "counters.record", "parts.manage", "warranties.manage", "vendors.manage", "attachments.add",
    ]),
    ("viewer", ("Viewer", "Leser", "Lettore"), []),
]


def clean(perms) -> str:
    """Only known keys, in catalogue order, as stored in Role.permissions."""
    wanted = set(perms or [])
    return ",".join(p for p in ALL if p in wanted)


def create_builtin_roles(db: Session, group: m.Group, lang: str = "en") -> dict[str, m.Role]:
    out = {}
    i = INDEX[norm(lang)]
    for key, names, perms in BUILTIN_ROLES:
        role = m.Role(group_id=group.id, key=key, name=names[i], permissions=clean(perms))
        db.add(role)
        out[key] = role
    db.flush()
    return out


def new_group(db: Session, name: str, owner: m.User) -> m.Group:
    """A group with the built-in roles and `owner` as its owner (and as their current group)."""
    g = m.Group(name=name)
    db.add(g)
    db.flush()
    roles = create_builtin_roles(db, g, owner.lang)
    db.add(m.Membership(user_id=owner.id, group_id=g.id, role_id=roles["owner"].id))
    owner.current_group_id = g.id
    db.flush()
    return g


@dataclass
class Ctx:
    """The logged-in user inside their active group."""
    user: m.User
    group: m.Group
    membership: m.Membership
    perms: set[str] = field(default_factory=set)

    @property
    def is_owner(self) -> bool:
        return self.membership.role.key == "owner"

    def can(self, perm: str) -> bool:
        return self.is_owner or perm in self.perms

    def need(self, perm: str) -> None:
        if not self.can(perm):
            label = PERMISSIONS.get(perm, (perm, perm, perm))[INDEX[norm(self.user.lang)]]
            msg = pick(self.user.lang, f"Your role does not allow: {label}", f"Din rolle har ikke lov til: {label}",
                       f"Il tuo ruolo non permette: {label}")
            raise HTTPException(403, msg)


def memberships_of(db: Session, user_id: int) -> list[m.Membership]:
    return db.scalars(select(m.Membership).where(m.Membership.user_id == user_id)
                      .order_by(m.Membership.joined_at, m.Membership.id)).all()


def group_ctx(
    user: m.User = Depends(current_user),
    db: Session = Depends(get_db),
    x_group_id: Optional[int] = Header(default=None),
) -> Ctx:
    """Active group: the X-Group-Id header if given, else the user's current group, else their first one."""
    mems = memberships_of(db, user.id)
    if not mems:
        raise HTTPException(403, "You are not a member of any group")
    wanted = x_group_id or user.current_group_id
    mem = next((x for x in mems if x.group_id == wanted), mems[0])
    return Ctx(user=user, group=mem.group, membership=mem, perms=mem.role.perm_set)


def require(*perms: str):
    """Dependency: the active group context, after checking the permission(s)."""
    def dep(ctx: Ctx = Depends(group_ctx)) -> Ctx:
        for p in perms:
            ctx.need(p)
        return ctx
    return dep


def group_asset_ids(db: Session, group_id: int):
    return select(m.Asset.id).where(m.Asset.group_id == group_id)


def migrate_to_groups(db: Session) -> Optional[str]:
    """Once, when groups arrive on a database that already has data: everything becomes one group.
    The first administrator is the owner, other administrators are admins, everyone else is a creator.
    Also run on later starts to pick up things left without a group (it then does nothing)."""
    users = db.scalars(select(m.User).order_by(m.User.id)).all()
    if not users:
        return None
    groups = db.scalars(select(m.Group).order_by(m.Group.id)).all()
    msg = None
    if not groups:
        owner = next((u for u in users if u.is_admin), users[0])
        name = default_group_name(owner.lang)
        g = new_group(db, name, owner)
        roles = {r.key: r for r in g.roles}
        for u in users:
            if u.id == owner.id:
                continue
            db.add(m.Membership(user_id=u.id, group_id=g.id,
                                role_id=roles["admin" if u.is_admin else "creator"].id))
            u.current_group_id = g.id
        msg = f"created group '{name}' with {len(users)} member(s), owner {owner.email}"
        groups = [g]
    if len(groups) == 1:  # only safe to adopt orphans when there is no doubt where they belong
        gid = groups[0].id
        orphans = 0
        for a in db.scalars(select(m.Asset).where(m.Asset.group_id.is_(None))):
            a.group_id = gid
            orphans += 1
        for v in db.scalars(select(m.Vendor).where(m.Vendor.group_id.is_(None))):
            v.group_id = gid
            orphans += 1
        if orphans:
            msg = (msg + "; " if msg else "") + f"{orphans} thing(s)/vendor(s) moved into it"
    db.commit()
    return msg
