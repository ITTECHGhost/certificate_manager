"""Registration records. No hard delete: important records are soft-deleted;
request steps are append-only."""
import hashlib

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone

UNITS = [
    ("student_affairs", "شؤون الطلبة"),
    ("finance", "المالية"),
    ("legal", "القانونية"),
]
HOLD_UNITS = [u for u in UNITS if u[0] in ("finance", "legal")]
HOLD_KIND_FOR_UNIT = {"finance": "financial", "legal": "legal"}


class LiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Tracked(models.Model):
    """created_at/created_by plus soft delete. delete() is refused."""

    created_at = models.DateTimeField("تاريخ الإنشاء", default=timezone.now, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="أنشأه",
                                   on_delete=models.PROTECT, null=True, blank=True,
                                   editable=False, related_name="+")
    deleted_at = models.DateTimeField("تاريخ الحذف", null=True, blank=True, editable=False)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="حذفه",
                                   on_delete=models.PROTECT, null=True, blank=True,
                                   editable=False, related_name="+")

    objects = LiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise PermissionDenied("الحذف النهائي غير مسموح؛ استخدم الأرشفة.")

    def soft_delete(self, user):
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["deleted_at", "deleted_by"])


class Student(Tracked):
    STUDY_TYPES = [("morning", "صباحي"), ("evening", "مسائي"), ("parallel", "موازي")]
    STATUSES = [
        ("new", "جديد"),
        ("in_review", "قيد التدقيق"),
        ("accepted", "مقبول"),
        ("rejected", "مرفوض"),
    ]
    name_ar = models.CharField("الاسم بالعربية", max_length=200, db_index=True)
    name_en = models.CharField("الاسم بالإنكليزية", max_length=200, blank=True)
    # Paper-form fields (day 3). Order/names to be matched to the real paper form.
    GENDERS = [("male", "ذكر"), ("female", "أنثى")]
    mother_name = models.CharField("اسم الأم الثلاثي", max_length=200, blank=True)
    birth_date = models.DateField("تاريخ الولادة", null=True, blank=True)
    birth_place = models.CharField("محل الولادة", max_length=100, blank=True)
    gender = models.CharField("الجنس", max_length=10, choices=GENDERS, blank=True)
    national_id = models.CharField("رقم البطاقة الوطنية", max_length=30, blank=True,
                                   db_index=True)
    phone = models.CharField("رقم الهاتف", max_length=20, blank=True)
    address = models.CharField("العنوان", max_length=300, blank=True)
    school_name = models.CharField("اسم المدرسة الإعدادية", max_length=200, blank=True)
    graduation_year = models.PositiveSmallIntegerField("سنة التخرج", null=True, blank=True)
    average = models.DecimalField("المعدل", max_digits=5, decimal_places=2, null=True,
                                  blank=True)
    department = models.CharField("القسم", max_length=150, db_index=True)
    study_type = models.CharField("نوع الدراسة", max_length=20, choices=STUDY_TYPES)
    status = models.CharField("الحالة", max_length=20, choices=STATUSES, default="new")

    class Meta:
        verbose_name = "طالب"
        verbose_name_plural = "الطلبة"
        ordering = ["name_ar"]

    def __str__(self):
        return self.name_ar


class StudentDocument(Tracked):
    KINDS = [
        ("id_card", "البطاقة الوطنية"),
        ("residence", "بطاقة السكن"),
        ("certificate", "وثيقة الإعدادية"),
        ("photo", "صورة شخصية"),
        ("other", "أخرى"),
    ]
    student = models.ForeignKey(Student, verbose_name="الطالب", on_delete=models.PROTECT,
                                related_name="documents")
    file = models.FileField("الملف", upload_to="student_docs/%Y/%m/")
    kind = models.CharField("النوع", max_length=20, choices=KINDS)
    pages = models.PositiveSmallIntegerField("عدد الصفحات", default=1)
    sha256 = models.CharField("البصمة", max_length=64, editable=False, db_index=True)

    class Meta:
        verbose_name = "وثيقة طالب"
        verbose_name_plural = "وثائق الطلبة"

    def save(self, *args, **kwargs):
        if self.file and not self.sha256:
            h = hashlib.sha256()
            for chunk in self.file.chunks():
                h.update(chunk)
            self.sha256 = h.hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_kind_display()} — {self.student}"


class Hold(Tracked):
    KINDS = [("financial", "مالي"), ("legal", "قانوني")]
    student = models.ForeignKey(Student, verbose_name="الطالب", on_delete=models.PROTECT,
                                related_name="holds")
    unit = models.CharField("الوحدة المالكة", max_length=20, choices=HOLD_UNITS)
    kind = models.CharField("نوع القيد", max_length=20, choices=KINDS, editable=False)
    note = models.TextField("الملاحظة", blank=True)
    is_open = models.BooleanField("مفتوح", default=True, editable=False)
    cleared_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="رفعه",
                                   on_delete=models.PROTECT, null=True, blank=True,
                                   editable=False, related_name="+")
    cleared_at = models.DateTimeField("تاريخ الرفع", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "قيد"
        verbose_name_plural = "القيود"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.kind = HOLD_KIND_FOR_UNIT[self.unit]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_kind_display()} — {self.student}"


class Request(Tracked):
    STATUSES = [("open", "مفتوح"), ("done", "مقبول"), ("rejected", "مرفوض")]
    student = models.ForeignKey(Student, verbose_name="الطالب", on_delete=models.PROTECT,
                                related_name="requests")
    title = models.CharField("الموضوع", max_length=200)
    current_unit = models.CharField("عند الوحدة", max_length=20, choices=UNITS)
    status = models.CharField("الحالة", max_length=20, choices=STATUSES, default="open")

    class Meta:
        verbose_name = "طلب"
        verbose_name_plural = "الطلبات"
        ordering = ["-created_at"]

    @property
    def stage_label(self):
        """«عند المالية» while open, else the final status («مقبول» / «مرفوض»)."""
        if self.status == "open":
            return f"عند {self.get_current_unit_display()}"
        return self.get_status_display()

    def __str__(self):
        return f"{self.title} — {self.student}"


class SignedCopy(Tracked):
    """Scanned signed copy of an accepted request (archive). Soft delete only."""

    request = models.ForeignKey(Request, verbose_name="الطلب", on_delete=models.PROTECT,
                                related_name="signed_copies")
    file = models.FileField("الملف", upload_to="signed_copies/%Y/%m/")
    sha256 = models.CharField("البصمة", max_length=64, editable=False, db_index=True)
    note = models.CharField("ملاحظة", max_length=200, blank=True)

    class Meta:
        verbose_name = "نسخة موقعة"
        verbose_name_plural = "النسخ الموقعة"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.request} — {self.created_at:%Y-%m-%d}"


class RequestStep(models.Model):
    """One movement of a request. Append-only: never edited, never deleted."""

    ACTIONS = [("send", "إرسال"), ("approve", "موافقة"), ("reject", "رفض"), ("note", "تهميش")]
    request = models.ForeignKey(Request, verbose_name="الطلب", on_delete=models.PROTECT,
                                related_name="steps")
    from_unit = models.CharField("من وحدة", max_length=20, choices=UNITS)
    to_unit = models.CharField("إلى وحدة", max_length=20, choices=UNITS)
    action = models.CharField("الإجراء", max_length=20, choices=ACTIONS)
    annotation = models.TextField("التهميش", blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="المستخدم",
                             on_delete=models.PROTECT, related_name="+")
    ip = models.GenericIPAddressField("عنوان IP", null=True, blank=True)
    created_at = models.DateTimeField("الوقت", default=timezone.now)

    class Meta:
        verbose_name = "خطوة طلب"
        verbose_name_plural = "خطوات الطلبات"
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionDenied("خطوات الطلب لا تُعدَّل.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("خطوات الطلب لا تُحذف.")

    def __str__(self):
        return f"{self.get_from_unit_display()} ← {self.get_to_unit_display()}"
