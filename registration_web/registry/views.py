from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
import io

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from openpyxl import Workbook
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from django.utils import timezone

from . import roster_export, services, uploads
from .forms import StudentForm
from .models import UNITS, Hold, Request, SignedCopy, Student, StudentDocument

SECTIONS = [
    ("البيانات الشخصية", ["name_ar", "name_en", "mother_name", "birth_date", "birth_place",
                          "gender", "national_id", "phone", "address"]),
    ("الدراسة الإعدادية", ["school_name", "graduation_year", "average"]),
    ("القبول", ["department", "study_type"]),
]


def _student_affairs(user):
    return user.is_superuser or "student_affairs" in services.user_units(user)


@login_required
def register(request):
    if not _student_affairs(request.user):
        raise PermissionDenied
    form = StudentForm(request.POST or None)
    if request.method == "POST":
        files = [(kind, f) for kind, _ in StudentDocument.KINDS
                 for f in request.FILES.getlist(f"doc_{kind}")]
        try:
            student = uploads.register_student(request.POST, files, request.user)
        except ValidationError as e:
            form.is_valid()
            for msg in e.messages:
                messages.error(request, msg)
        else:
            messages.success(request, f"حُفظ الطالب {student} مع {len(files)} وثيقة.")
            return redirect(reverse("admin:registry_student_change", args=[student.pk]))
    sections = [(title, [form[n] for n in names]) for title, names in SECTIONS]
    return render(request, "registry/register.html",
                  {**admin.site.each_context(request), "sections": sections,
                   "kinds": StudentDocument.KINDS, "title": "استمارة التسجيل"})


@login_required
def document_file(request, pk):
    """Files are never public: login + unit check, then stream the file."""
    if not _student_affairs(request.user):
        raise PermissionDenied
    doc = get_object_or_404(StudentDocument, pk=pk)
    try:
        return FileResponse(doc.file.open("rb"))
    except FileNotFoundError:
        raise Http404


@login_required
def request_detail(request, pk):
    """Status + step history; the holding unit sends it on (with annotation) or accepts it."""
    if not (request.user.is_superuser or services.user_units(request.user)):
        raise PermissionDenied
    req = get_object_or_404(Request, pk=pk)
    can_move = req.status == "open" and services.holds_request(request.user, req)
    if request.method == "POST":
        if not can_move:
            raise PermissionDenied
        ip = request.META.get("REMOTE_ADDR")  # LAN only, no proxy in front
        note = request.POST.get("annotation", "").strip()
        try:
            if request.POST.get("action") == "accept":
                services.accept_request(req, request.user, ip=ip, annotation=note)
                messages.success(request, "قُبل الطلب.")
            elif request.POST.get("action") == "reject":
                services.reject_request(req, request.user, ip=ip, annotation=note)
                messages.success(request, "رُفض الطلب.")
            else:
                services.send_request(req, request.POST.get("to_unit", ""), request.user,
                                      ip=ip, annotation=note)
                messages.success(request, "أُرسل الطلب.")
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)
        return redirect(reverse("request_detail", args=[req.pk]))
    targets = [u for u in UNITS if u[0] != req.current_unit]
    can_sign = req.status == "done" and uploads.can_manage_signed(
        request.user, req, services.user_units)
    return render(request, "registry/request_detail.html",
                  {**admin.site.each_context(request), "req": req, "can_move": can_move,
                   "can_sign": can_sign,
                   "signed": req.signed_copies.all() if can_sign else [],
                   "steps": req.steps.select_related("user"), "targets": targets,
                   "title": f"الطلب: {req.title}"})


@login_required
def student_holds(request, pk):
    """All holds of a student the user may see; only the owning unit clears (server-checked)."""
    if not (request.user.is_superuser or services.user_units(request.user)):
        raise PermissionDenied
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        hold = get_object_or_404(Hold, pk=request.POST.get("hold"), student=student)
        if not services.can_edit_hold(request.user, hold):
            raise PermissionDenied
        services.clear_hold(hold, request.user)
        messages.success(request, "رُفع القيد.")
        return redirect(reverse("student_holds", args=[student.pk]))
    holds = [h for h in student.holds.select_related("cleared_by", "created_by")
             if services.can_view_hold(request.user, h)]
    rows = [(h, h.is_open and services.can_edit_hold(request.user, h)) for h in holds]
    return render(request, "registry/student_holds.html",
                  {**admin.site.each_context(request), "student": student, "rows": rows,
                   "title": f"قيود الطالب: {student}"})


INBOX_PAGE_SIZE = 25


@login_required
def inbox(request):
    """Open requests held NOW by the user's own units, newest first. The unit filter is applied
    before the search, so a search can never reach another unit's requests."""
    if request.user.is_superuser:
        qs = Request.objects.all()
    else:
        units = services.user_units(request.user)
        if not units:
            raise PermissionDenied
        qs = Request.objects.filter(current_unit__in=units)
    qs = qs.filter(status="open").select_related("student")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(student__name_ar__icontains=q) | Q(student__national_id__icontains=q))
    qs = qs.order_by("-created_at", "-pk")
    page = Paginator(qs, INBOX_PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "registry/inbox.html",
                  {**admin.site.each_context(request), "page": page, "q": q,
                   "title": "صندوق الوارد"})


def _signed_allowed(user, req):
    if not uploads.can_manage_signed(user, req, services.user_units):
        raise PermissionDenied


@login_required
@require_POST
def signed_upload(request, pk):
    """Upload a scanned signed copy to an accepted request (holding unit / Student Affairs)."""
    req = get_object_or_404(Request, pk=pk)
    _signed_allowed(request.user, req)
    f = request.FILES.get("file")
    try:
        if not f:
            raise ValidationError("اختر ملفًا.")
        uploads.add_signed_copy(req, f, request.user, request.POST.get("note", ""))
        messages.success(request, "حُفظت النسخة الموقعة.")
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
    return redirect(reverse("request_detail", args=[req.pk]))


@login_required
@require_POST
def signed_delete(request, pk):
    """Soft delete only: the row and the file stay."""
    sc = get_object_or_404(SignedCopy, pk=pk)
    _signed_allowed(request.user, sc.request)
    sc.soft_delete(request.user)
    messages.success(request, "أُزيلت النسخة الموقعة (أرشفة).")
    return redirect(reverse("request_detail", args=[sc.request_id]))


@login_required
def signed_file(request, pk):
    """Files are never public: login + unit check, then stream the file."""
    sc = get_object_or_404(SignedCopy, pk=pk)
    _signed_allowed(request.user, sc.request)
    try:
        return FileResponse(sc.file.open("rb"))
    except FileNotFoundError:
        raise Http404


@login_required
def rejected(request):
    """«مرفوضة»: rejected requests of the user's own units (the unit that rejected keeps
    current_unit). Unit filter BEFORE search; Student Affairs and superuser see all."""
    if _student_affairs(request.user):
        qs = Request.objects.all()
    else:
        units = services.user_units(request.user)
        if not units:
            raise PermissionDenied
        qs = Request.objects.filter(current_unit__in=units)
    qs = qs.filter(status="rejected").select_related("student")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(student__name_ar__icontains=q) | Q(student__national_id__icontains=q))
    qs = qs.order_by("-created_at", "-pk")
    page = Paginator(qs, INBOX_PAGE_SIZE).get_page(request.GET.get("page"))
    for r in page.object_list:
        step = r.steps.filter(action="reject").order_by("-created_at", "-pk").first()
        r.reject_reason = step.annotation if step else ""
    return render(request, "registry/rejected.html",
                  {**admin.site.each_context(request), "page": page, "q": q,
                   "title": "الطلبات المرفوضة"})


@login_required
def student_card(request, pk):
    """Printable student ID card. Student Affairs only. Fields are a guess until the real card."""
    if not _student_affairs(request.user):
        raise PermissionDenied
    return render(request, "registry/student_card.html",
                  {"student": get_object_or_404(Student, pk=pk)})


# Columns of the university e-mail sheet. TODO: replace with the real sample's columns.
EXPORT_COLUMNS = [("name_ar", "الاسم بالعربية"), ("name_en", "الاسم بالإنكليزية"),
                  ("department", "القسم"), ("national_id", "رقم البطاقة الوطنية"),
                  ("phone", "رقم الهاتف")]


def export_students_xlsx(students):
    wb = Workbook()
    ws = wb.active
    ws.title = "students"
    ws.sheet_view.rightToLeft = True
    ws.append([label for _, label in EXPORT_COLUMNS])
    for s in students:
        ws.append([getattr(s, f) or "" for f, _ in EXPORT_COLUMNS])
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type=(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    resp["Content-Disposition"] = 'attachment; filename="students_email.xlsx"'
    return resp


@login_required
def roster_export_view(request):
    """Accepted students of one department -> xlsx for the Windows program's bulk import.
    Student Affairs only; read only (never MySQL)."""
    if not _student_affairs(request.user):
        raise PermissionDenied
    dept = request.GET.get("department", "").strip()
    year = request.GET.get("admission_year", "").strip()
    if dept:
        try:
            data = roster_export.accepted_roster_xlsx(dept, year)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            resp = HttpResponse(data, content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
            stamp = timezone.localdate().strftime("%Y%m%d")
            resp["Content-Disposition"] = f'attachment; filename="accepted_{stamp}.xlsx"'
            return resp
    return render(request, "registry/roster_export.html",
                  {**admin.site.each_context(request), "departments":
                   roster_export.accepted_departments(), "dept": dept, "year": year,
                   "title": "تصدير المقبولين إلى برنامج الشهادات"})


@login_required
def student_export(request):
    """Excel of ONLY the requested students (?ids=1,2,3); Student Affairs only; read only."""
    if not _student_affairs(request.user):
        raise PermissionDenied
    ids = [int(x) for x in request.GET.get("ids", "").split(",") if x.strip().isdigit()]
    return export_students_xlsx(Student.objects.filter(pk__in=ids).order_by("name_ar"))
