# Overnight plan 04 — صفحة قوائم الترتيب الرسمية (2026-11-20, DEV)

1. Server (`routers/official_rankings.py`): `GET /page` (بحث + ترقيم، `deleted_at IS NULL`)؛ التحقق من المستخدم: `personnel_id` فعّال + (مسؤول أو `page:rankings`/`page:orders`) على كل كتابة؛ الحذف soft delete.
2. Migration `0010_official_rankings_soft_delete.sql` + rollback (يُكتب فقط، لا يُشغَّل). الكود يعمل قبل التشغيل (يتحقق من وجود العمود).
3. Client: `data/repositories/official_rankings.py` (`page`, تمرير `personnel_id`)، شاشة جديدة `nicegui_screens/official_rankings_screen.py` (قائمة مرقّمة + بحث + عرض الأسماء مع ربط يدوي + استيراد) وبند «rankings» في القائمة الجانبية.
4. زر الحوار القديم في أوامر التخرج يبقى كما هو (لا حذف ملفات).
5. Tests first: `tests/test_official_rankings_page.py` (بيانات وهمية فقط). تجربة ملف Excel حقيقي: تحتاج ملف المستخدم — تُترك.
6. Limits: الخادم لا يملك توكن لكل مستخدم (ثغرة معروفة) فالتحقق يعتمد `personnel_id` المُرسل؛ يصير حقيقيًا مع خطة التوكن.
