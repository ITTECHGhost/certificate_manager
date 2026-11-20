from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from django.views.generic import RedirectView

from registry import views

admin.site.site_header = "نظام التسجيل"
admin.site.site_title = "نظام التسجيل"
admin.site.index_title = "لوحة الإدارة"
admin.site.site_url = "/inbox/"  # header link «عرض الموقع» → the user's unit inbox

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
    path("register/", views.register, name="register"),
    path("documents/<int:pk>/", views.document_file, name="document_file"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("students/<int:pk>/holds/", views.student_holds, name="student_holds"),
    path("inbox/", views.inbox, name="inbox"),
    path("rejected/", views.rejected, name="rejected"),
    path("requests/<int:pk>/signed/", views.signed_upload, name="signed_upload"),
    path("signed/<int:pk>/", views.signed_file, name="signed_file"),
    path("signed/<int:pk>/delete/", views.signed_delete, name="signed_delete"),
    path("students/<int:pk>/card/", views.student_card, name="student_card"),
    path("students/export/", views.student_export, name="student_export"),
    # Static files (admin CSS/JS) served by the app itself: LAN only, small load, no WhiteNoise.
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
]
# Media (student documents) is NOT public, not even in DEBUG: only documents/<pk>/ serves it.
