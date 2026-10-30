"""Data model.

Asset        = the thing being maintained (house, car, boat, cabin ...)
Component    = a part of an asset (heat pump, roof, engine, tyres ...)
Task         = a recurring or one-off maintenance job, on an asset or a component
Completion   = history: each time a task was done, with cost and notes
SparePart    = parts and consumables; flagged parts form the shopping list
Purchase     = a part bought (quantity, price) – counts as cost, like a completion
Warranty     = warranties with an end date (shown in the calendar)
Attachment   = files (receipts, manuals, photos) linked to any of the above
CounterReading = km / engine-hour readings of an asset (the latest one is the current value)
Vendor       = craftsmen and companies a task can be handed to (contact data, rate)

Group        = a household / club that owns things; every asset and vendor belongs to one group
Role         = a named set of permissions inside a group (Owner, Admin, Creator, Viewer + own ones)
Membership   = user X is in group Y with role Z (one person can be in several groups)
Invitation   = an e-mailed one-time link that adds someone to a group with a role
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))
    lang: Mapped[str] = mapped_column(String(5), default="en")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    ical_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # the group the app shows; None = the first group the user is a member of
    current_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)
    # goes up by one when the password is reset: log-ins (tokens) made before that stop working
    session_version: Mapped[int] = mapped_column(Integer, default=0)
    # set from TotalMant Admin: the person can't log in until unblocked
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    roles: Mapped[list["Role"]] = relationship(back_populates="group", cascade="all, delete-orphan",
                                               order_by="Role.id")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Role(Base):
    """key is "owner", "admin", "creator" or "viewer" for the built-in roles, None for roles the admin made.
    permissions: comma-separated keys from permissions.PERMISSIONS (Owner always has all of them)."""
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    key: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(60))
    permissions: Mapped[str] = mapped_column(Text, default="")

    group: Mapped[Group] = relationship(back_populates="roles")

    @property
    def perm_set(self) -> set[str]:
        return {p for p in (self.permissions or "").split(",") if p}


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "group_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()
    group: Mapped[Group] = relationship(back_populates="memberships")
    role: Mapped[Role] = relationship()


class Event(Base):
    """What happened on the server (sign-ups, log-ins, e-mails, backups ...), shown in TotalMant Admin.
    Only who/what/when: never the content of a family's things."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    text: Mapped[str] = mapped_column(String(300), default="")  # English, also for searching and older rows
    # the same sentence as a key + values, so TotalMant Admin can show it in the viewer's language
    msg: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)


class Setting(Base):
    """Server settings changed from TotalMant Admin; they win over the values in .env."""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class PasswordReset(Base):
    """A "forgot password" link. Only a hash of the token is stored, so a copy of the database can't be used to log in."""
    __tablename__ = "password_resets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(200))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invited_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped[Group] = relationship()
    role: Mapped[Role] = relationship()
    invited_by: Mapped[Optional[User]] = relationship()


class Vendor(Base):
    """A company or craftsman that can be given a task (plumber, boatyard, car workshop ...)."""
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    company: Mapped[str] = mapped_column(String(150))
    contact_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    trade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # plumber, electrician ...
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    org_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    hourly_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rate_notes: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)  # call-out fee, fixed prices ...
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(30), default="home")  # home, car, boat, cabin, bicycle, motorcycle, scooter, other
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # usage counter for counter-based tasks: "none", "km" or "hours" (engine hours)
    counter_unit: Mapped[str] = mapped_column(String(10), default="none")
    counter_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    counter_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    components: Mapped[list["Component"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    parts: Mapped[list["SparePart"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    warranties: Mapped[list["Warranty"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class CounterReading(Base):
    __tablename__ = "counter_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    reading_on: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    recorded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Component(Base):
    __tablename__ = "components"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    installed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    asset: Mapped[Asset] = relationship(back_populates="components")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[Optional[int]] = mapped_column(ForeignKey("components.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Recurrence: interval_unit in {"none", "days", "weeks", "months", "years"}
    interval_value: Mapped[int] = mapped_column(Integer, default=0)
    interval_unit: Mapped[str] = mapped_column(String(10), default="none")
    next_due: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    remind_days_before: Mapped[int] = mapped_column(Integer, default=7)
    # counter-based recurrence (on top of, or instead of, the time interval): "every 100 h"
    counter_interval: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    counter_next_due: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    counter_remind_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # job given to the vendor: None (not asked yet), "requested", "confirmed" (with a date)
    vendor_status: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    vendor_requested_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    vendor_booked_for: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_reminded_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped[Asset] = relationship(back_populates="tasks")
    component: Mapped[Optional[Component]] = relationship()
    assigned_to: Mapped[Optional[User]] = relationship(foreign_keys=[assigned_to_id])
    created_by: Mapped[Optional[User]] = relationship(foreign_keys=[created_by_id])
    vendor: Mapped[Optional[Vendor]] = relationship()
    completions: Mapped[list["Completion"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="Completion.done_on.desc()"
    )


class Completion(Base):
    __tablename__ = "completions"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    done_on: Mapped[date] = mapped_column(Date)
    done_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    counter_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # km / hours when it was done
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)

    task: Mapped[Task] = relationship(back_populates="completions")
    done_by: Mapped[Optional[User]] = relationship()
    vendor: Mapped[Optional["Vendor"]] = relationship()


class SparePart(Base):
    __tablename__ = "spare_parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[Optional[int]] = mapped_column(ForeignKey("components.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(150))
    part_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)  # vendor's name, kept for old data
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    qty_in_stock: Mapped[int] = mapped_column(Integer, default=0)
    min_qty: Mapped[int] = mapped_column(Integer, default=0)
    on_shopping_list: Mapped[bool] = mapped_column(Boolean, default=False)
    qty_to_buy: Mapped[int] = mapped_column(Integer, default=1)

    asset: Mapped[Asset] = relationship(back_populates="parts")
    component: Mapped[Optional[Component]] = relationship()
    vendor: Mapped[Optional[Vendor]] = relationship()


class Purchase(Base):
    """A spare part bought: adds to stock and counts as money spent on the asset."""
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    part_id: Mapped[Optional[int]] = mapped_column(ForeignKey("spare_parts.id", ondelete="SET NULL"), nullable=True)
    part_name: Mapped[str] = mapped_column(String(150))  # kept even if the part is deleted later
    bought_on: Mapped[date] = mapped_column(Date, index=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bought_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    asset: Mapped[Asset] = relationship()
    bought_by: Mapped[Optional[User]] = relationship()


class Warranty(Base):
    __tablename__ = "warranties"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[Optional[int]] = mapped_column(ForeignKey("components.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(150))
    provider: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    asset: Mapped[Asset] = relationship(back_populates="warranties")
    component: Mapped[Optional[Component]] = relationship()


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    # entity_type in {"asset", "component", "task", "completion", "part", "warranty"}
    entity_type: Mapped[str] = mapped_column(String(20), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
