from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

IntervalUnit = Literal["none", "days", "weeks", "months", "years"]
AssetKind = Literal["home", "car", "boat", "cabin", "bicycle", "motorcycle", "scooter", "other"]
CounterUnit = Literal["none", "km", "hours"]
VendorStatus = Literal["none", "requested", "confirmed"]
Lang = Literal["en", "no", "it"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- users / auth ----------
class SetupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    lang: Lang = "en"
    group_name: Optional[str] = Field(default=None, max_length=100)  # "Family" when left empty


class SignupIn(SetupIn):
    group_name: str = Field(min_length=1, max_length=100)
    code: str = ""  # only needed when SIGNUP_CODE is set


class LoginIn(BaseModel):
    email: str
    password: str


class UserCreate(SetupIn):
    role_id: Optional[int] = None  # default: Creator
    is_admin: Optional[bool] = None  # older app versions: True = Admin role


class UserUpdate(BaseModel):
    name: Optional[str] = None
    lang: Optional[Lang] = None
    email_reminders: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)
    is_admin: Optional[bool] = None  # older app versions; use role_id
    role_id: Optional[int] = None


class UserOut(ORM):
    id: int
    name: str
    email: str
    lang: str
    is_admin: bool
    email_reminders: bool


class TokenOut(BaseModel):
    token: str
    user: UserOut


# ---------- groups, members, roles, invitations ----------
class MemberOut(UserOut):
    role_id: int
    role_name: str
    role_key: Optional[str] = None


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupOut(GroupIn):
    id: int


class NewGroupIn(GroupIn):
    code: str = ""  # only needed when SIGNUP_CODE is set


class SwitchGroupIn(BaseModel):
    group_id: int


class TransferIn(BaseModel):
    user_id: int


class RoleIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    permissions: list[str] = []


class RoleOut(BaseModel):
    id: int
    key: Optional[str] = None
    name: str
    permissions: list[str]
    members: int = 0
    locked: bool = False   # Owner: always every permission
    builtin: bool = False  # built-in roles can't be deleted


class InvitationIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    role_id: Optional[int] = None
    lang: Optional[Lang] = None  # language of the e-mail; default: yours


class InvitationOut(BaseModel):
    id: int
    email: str
    role_id: int
    role_name: str
    link: str
    expires_at: datetime
    created_at: datetime
    invited_by_name: Optional[str] = None
    mailed: bool = False
    mail_error: Optional[str] = None


class ForgotIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    lang: Optional[Lang] = None  # language of the e-mail; default: the user's own


class ResetIn(BaseModel):
    password: str = Field(min_length=6, max_length=200)


class AcceptIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)  # only for a new account
    password: str = Field(min_length=6, max_length=200)
    lang: Lang = "en"


# ---------- assets / components ----------
class AssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    kind: AssetKind = "home"
    description: Optional[str] = None
    location: Optional[str] = None
    counter_unit: CounterUnit = "none"
    counter_value: Optional[float] = Field(default=None, ge=0)  # current km / hours; a change is logged as a reading


class AssetOut(ORM, AssetIn):
    id: int
    counter_on: Optional[date] = None


class CounterIn(BaseModel):
    value: float = Field(ge=0)
    reading_on: date = Field(default_factory=date.today)


class CounterReadingOut(ORM):
    id: int
    reading_on: date
    value: float


class AssetSummary(AssetOut):
    task_count: int = 0
    overdue_count: int = 0
    due_soon_count: int = 0
    total_cost: float = 0.0


class ComponentIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installed_on: Optional[date] = None
    notes: Optional[str] = None


class ComponentOut(ORM, ComponentIn):
    id: int
    asset_id: int


# ---------- tasks / history ----------
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    component_id: Optional[int] = None
    interval_value: int = Field(default=0, ge=0)
    interval_unit: IntervalUnit = "none"
    next_due: Optional[date] = None
    remind_days_before: int = Field(default=7, ge=0, le=365)
    assigned_to_id: Optional[int] = None
    vendor_id: Optional[int] = None
    estimated_cost: Optional[float] = None
    active: bool = True
    counter_interval: Optional[float] = Field(default=None, ge=0)
    counter_next_due: Optional[float] = Field(default=None, ge=0)
    counter_remind_before: Optional[float] = Field(default=None, ge=0)


class CompletionIn(BaseModel):
    done_on: date = Field(default_factory=date.today)
    cost: Optional[float] = None
    notes: Optional[str] = None
    counter_value: Optional[float] = Field(default=None, ge=0)
    vendor_id: Optional[int] = None  # who did the job, if not done by the household


class VendorStatusIn(BaseModel):
    status: VendorStatus
    on: Optional[date] = None  # requested: the day asked (default today); confirmed: the agreed date


class CompletionOut(ORM):
    id: int
    task_id: int
    done_on: date
    cost: Optional[float]
    notes: Optional[str]
    done_by_name: Optional[str] = None
    counter_value: Optional[float] = None
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None


class TaskOut(ORM):
    id: int
    asset_id: int
    asset_name: str = ""
    asset_kind: str = ""
    component_id: Optional[int]
    component_name: Optional[str] = None
    title: str
    description: Optional[str]
    interval_value: int
    interval_unit: str
    next_due: Optional[date]
    remind_days_before: int
    assigned_to_id: Optional[int]
    assigned_to_name: Optional[str] = None
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    vendor_phone: Optional[str] = None
    vendor_email: Optional[str] = None
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    vendor_status: Optional[str] = None
    vendor_requested_on: Optional[date] = None
    vendor_booked_for: Optional[date] = None
    counter_unit: Optional[str] = None  # set only when the task follows the asset's counter
    counter_interval: Optional[float] = None
    counter_next_due: Optional[float] = None
    counter_remind_before: Optional[float] = None
    counter_current: Optional[float] = None
    counter_left: Optional[float] = None
    estimated_cost: Optional[float]
    active: bool
    status: str = "ok"  # overdue | due_soon | ok | none | inactive
    last_done: Optional[date] = None
    total_cost: float = 0.0


class TaskDetail(TaskOut):
    completions: list[CompletionOut] = []


# ---------- vendors ----------
class VendorIn(BaseModel):
    company: str = Field(min_length=1, max_length=150)
    contact_name: Optional[str] = None
    trade: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    org_number: Optional[str] = None
    website: Optional[str] = None
    hourly_rate: Optional[float] = Field(default=None, ge=0)
    rate_notes: Optional[str] = None
    notes: Optional[str] = None
    active: bool = True


class VendorOut(ORM, VendorIn):
    id: int
    open_tasks: int = 0


class VendorJob(BaseModel):
    completion_id: int
    task_id: int
    task_title: str
    asset_id: int
    asset_name: str
    done_on: date
    cost: Optional[float] = None
    notes: Optional[str] = None


class VendorHistory(BaseModel):
    vendor: VendorOut
    open_tasks: list["TaskOut"] = []
    jobs: list[VendorJob] = []
    total_spent: float = 0.0
    spent_this_year: float = 0.0


# ---------- parts / warranties ----------
class PartIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    component_id: Optional[int] = None
    part_number: Optional[str] = None
    supplier: Optional[str] = None
    vendor_id: Optional[int] = None  # the supplier, from the same vendor list as the tasks
    url: Optional[str] = None
    unit_price: Optional[float] = None
    qty_in_stock: int = 0
    min_qty: int = 0
    on_shopping_list: bool = False
    qty_to_buy: int = 1


class PartOut(ORM, PartIn):
    id: int
    asset_id: int
    asset_name: str = ""
    component_name: Optional[str] = None
    below_min: bool = False
    last_purchase_id: Optional[int] = None


class PurchaseIn(BaseModel):
    qty: int = Field(default=1, ge=1)
    unit_price: Optional[float] = Field(default=None, ge=0)
    bought_on: date = Field(default_factory=date.today)


class PurchaseOut(ORM):
    id: int
    asset_id: int
    part_id: Optional[int]
    part_name: str
    bought_on: date
    qty: int
    unit_price: Optional[float]
    total: Optional[float]


class WarrantyIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    component_id: Optional[int] = None
    provider: Optional[str] = None
    reference: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class WarrantyOut(ORM, WarrantyIn):
    id: int
    asset_id: int
    asset_name: str = ""
    component_name: Optional[str] = None
    expired: bool = False


# ---------- attachments ----------
class AttachmentOut(ORM):
    id: int
    entity_type: str
    entity_id: int
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime


# ---------- asset detail ----------
class AssetDetail(AssetOut):
    components: list[ComponentOut] = []
    tasks: list[TaskOut] = []
    parts: list[PartOut] = []
    warranties: list[WarrantyOut] = []
    attachments: list[AttachmentOut] = []
    total_cost: float = 0.0
    readings: list[CounterReadingOut] = []
