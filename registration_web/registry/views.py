from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import services, uploads
from .forms import StudentForm
from .models import UNITS, Request, StudentDocument

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
            else:
                services.send_request(req, request.POST.get("to_unit", ""), request.user,
                                      ip=ip, annotation=note)
                messages.success(request, "أُرسل الطلب.")
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)
        return redirect(reverse("request_detail", args=[req.pk]))
    targets = [u for u in UNITS if u[0] != req.current_unit]
    return render(request, "registry/request_detail.html",
                  {**admin.site.each_context(request), "req": req, "can_move": can_move,
                   "steps": req.steps.select_related("user"), "targets": targets,
                   "title": f"الطلب: {req.title}"})
