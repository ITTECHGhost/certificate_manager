from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.html import format_html

from . import services
from .models import Hold, Request, RequestStep, Student, StudentDocument


class TrackedAdmin(admin.ModelAdmin):
    list_per_page = 50
    readonly_fields = ("created_at", "created_by")

    def get_queryset(self, request):
        return self.model.objects.all()  # soft-deleted rows stay hidden

    def has_delete_permission(self, request, obj=None):
        return False  # no hard delete anywhere

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class DocumentInline(admin.TabularInline):
    model = StudentDocument
    extra = 0
    fields = ("kind", "open_file", "pages", "sha256", "created_at")
    readonly_fields = ("open_file", "sha256", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # uploads go through /register/ (temp file -> commit -> rename)

    @admin.display(description="الملف")
    def open_file(self, obj):
        if not obj.pk:
            return "-"
        return format_html('<a href="{}" target="_blank">فتح</a>',
                           reverse("document_file", args=[obj.pk]))


class HoldInline(admin.TabularInline):
    model = Hold
    extra = 0
    fields = ("unit", "kind", "note", "is_open", "cleared_by", "cleared_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Student)
class StudentAdmin(TrackedAdmin):
    list_display = ("name_ar", "name_en", "department", "study_type", "status", "created_at")
    list_filter = ("status", "study_type", "department")
    search_fields = ("name_ar", "name_en", "department")
    inlines = [DocumentInline, HoldInline]

    def save_formset(self, request, form, formset, change):
        for obj in formset.save(commit=False):
            if obj.pk is None:
                obj.created_by = request.user
            obj.save()


@admin.register(StudentDocument)
class StudentDocumentAdmin(TrackedAdmin):
    list_display = ("student", "kind", "pages", "sha256", "created_at")
    list_filter = ("kind",)
    search_fields = ("student__name_ar", "sha256")
    readonly_fields = ("file", "sha256", "created_at", "created_by")
    autocomplete_fields = ("student",)

    def has_add_permission(self, request):
        return False  # uploads go through /register/ (temp file -> commit -> rename)


@admin.register(Hold)
class HoldAdmin(TrackedAdmin):
    list_display = ("student", "unit", "kind", "is_open", "created_at", "cleared_at")
    list_filter = ("unit", "kind", "is_open")
    search_fields = ("student__name_ar", "note")
    readonly_fields = ("kind", "is_open", "cleared_by", "cleared_at", "created_at", "created_by")
    autocomplete_fields = ("student",)
    actions = ["clear_selected"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        units = services.user_units(request.user)
        if request.user.is_superuser or "student_affairs" in units:
            return qs
        return qs.filter(unit__in=units)

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        return obj is None or services.can_edit_hold(request.user, obj)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "unit" and not request.user.is_superuser:
            units = services.user_units(request.user)
            kwargs["choices"] = [c for c in db_field.choices if c[0] in units]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not services.can_edit_hold(request.user, obj):
            raise PermissionDenied("لا يعدّل القيد إلا الوحدة المالكة له.")
        super().save_model(request, obj, form, change)

    @admin.action(description="رفع القيود المحددة")
    def clear_selected(self, request, queryset):
        for hold in queryset:
            services.clear_hold(hold, request.user)  # raises -> whole request rolls back
        self.message_user(request, f"رُفع {queryset.count()} قيد.")


class StepInline(admin.TabularInline):
    model = RequestStep
    extra = 0
    fields = ("created_at", "from_unit", "to_unit", "action", "annotation", "user", "ip")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Request)
class RequestAdmin(TrackedAdmin):
    list_display = ("title", "student", "stage", "created_at", "open_link")

    @admin.display(description="الحالة")
    def stage(self, obj):
        return obj.stage_label

    @admin.display(description="الإرسال والسجل")
    def open_link(self, obj):
        return format_html('<a href="{}">فتح</a>', reverse("request_detail", args=[obj.pk]))
    list_filter = ("current_unit", "status")
    search_fields = ("title", "student__name_ar")
    autocomplete_fields = ("student",)
    inlines = [StepInline]


@admin.register(RequestStep)
class RequestStepAdmin(admin.ModelAdmin):
    list_display = ("request", "from_unit", "to_unit", "action", "user", "ip", "created_at")
    list_filter = ("from_unit", "to_unit", "action")
    search_fields = ("request__title", "request__student__name_ar", "annotation")
    list_per_page = 50

    def has_add_permission(self, request):
        return False  # steps are written by services.send_request only

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
