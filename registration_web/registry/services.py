"""Server-side rules. The admin and later views call these; never bypass them."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Hold, Request, RequestStep, UNITS

UNIT_CODES = {code for code, _ in UNITS}


def user_units(user):
    """Unit codes the user belongs to (group name == unit code)."""
    return set(user.groups.filter(name__in=UNIT_CODES).values_list("name", flat=True))


def can_view_hold(user, hold):
    if user.is_superuser:
        return True
    units = user_units(user)
    return "student_affairs" in units or hold.unit in units


def can_edit_hold(user, hold):
    """Only the owning unit edits or clears a hold."""
    return user.is_superuser or hold.unit in user_units(user)


@transaction.atomic
def clear_hold(hold, user):
    hold = Hold.objects.select_for_update().get(pk=hold.pk)
    if not can_edit_hold(user, hold):
        raise PermissionDenied("لا يرفع القيد إلا الوحدة المالكة له.")
    if not hold.is_open:
        return hold
    hold.is_open = False
    hold.cleared_by = user
    hold.cleared_at = timezone.now()
    hold.save(update_fields=["is_open", "cleared_by", "cleared_at"])
    return hold


def holds_request(user, req):
    """Only the unit the request is at may move or accept it."""
    return user.is_superuser or req.current_unit in user_units(user)


def _check_can_move(req, user):
    if not holds_request(user, req):
        raise PermissionDenied("لا يحرّك الطلب إلا الوحدة التي هو عندها.")
    if req.status != "open":
        raise ValidationError("الطلب مغلق.")


@transaction.atomic
def send_request(req, to_unit, user, ip=None, annotation="", action="send"):
    """Move a request to another unit: one step row + the request's unit, together."""
    req = Request.objects.select_for_update().get(pk=req.pk)
    _check_can_move(req, user)
    if to_unit not in UNIT_CODES:
        raise ValidationError({"to_unit": "وحدة غير معروفة."})
    step = RequestStep(
        request=req, from_unit=req.current_unit, to_unit=to_unit, action=action,
        annotation=annotation, user=user, ip=ip,
    )
    step.full_clean()
    step.save()
    req.current_unit = to_unit
    req.save(update_fields=["current_unit"])
    return step


@transaction.atomic
def accept_request(req, user, ip=None, annotation=""):
    """Final acceptance by the holding unit: an approve step + status done, together."""
    req = Request.objects.select_for_update().get(pk=req.pk)
    _check_can_move(req, user)
    step = RequestStep(
        request=req, from_unit=req.current_unit, to_unit=req.current_unit,
        action="approve", annotation=annotation, user=user, ip=ip,
    )
    step.full_clean()
    step.save()
    req.status = "done"
    req.save(update_fields=["status"])
    return step


@transaction.atomic
def reject_request(req, user, ip=None, annotation=""):
    """Rejection by the holding unit: a reject step (reason required) + status rejected, together."""
    req = Request.objects.select_for_update().get(pk=req.pk)
    _check_can_move(req, user)
    annotation = (annotation or "").strip()
    if not annotation:
        raise ValidationError({"annotation": "سبب الرفض (التهميش) مطلوب."})
    step = RequestStep(
        request=req, from_unit=req.current_unit, to_unit=req.current_unit,
        action="reject", annotation=annotation, user=user, ip=ip,
    )
    step.full_clean()
    step.save()
    req.status = "rejected"
    req.save(update_fields=["status"])
    return step
