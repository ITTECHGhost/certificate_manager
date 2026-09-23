# دليل استخدام المتغيرات في قالب الوثيقة (Jinja2 Template Variable Map)

يحتوي هذا الدليل على جميع المتغيرات (Variables) التي يتم تمريرها من النظام إلى قالب الـ Word (docxtpl) لتوليد وثائق التخرج. يمكنك نسخ هذه المتغيرات ولصقها مباشرة في ملف الـ Word الخاص بك.

## 1. المعلومات الشخصية والأكاديمية للطالب (Demographics)
توضع هذه المتغيرات بشكل مباشر في النص (خارج الجداول الدورية).

| الوصف (Description) | المتغير في الـ Word (Jinja2 Tag) |
| :--- | :--- |
| **اسم الطالب** | `{{ student_name }}` |
| **العنوان (إلى من يهمه الأمر / Title)** | `{{ Title }}` أو `{{ to_title }}` |
| **تاريخ التلولد** | `{{ Birthday }}` |
| **محل الولادة** | `{{ Birthplace }}` |
| **الجنسية** | `{{ Nationality }}` |
| **القسم الأكاديمي** | `{{ department_id }}` |
| **نوع الدراسة (صباحية/مسائية)** | `{{ study_type }}` |
| **سنة القبول** | `{{ admission_year }}` |
| **سنة التخرج** | `{{ graduation_year }}` |
| **تاريخ التخرج** | `{{ graduation_date }}` |
| **الدور (فصل التخرج الأول/الثاني/صيفي)** | `{{ graduation_semester }}` |
| **المعدل التراكمي (3 مراتب عشرية)** | `{{ average }}` |
| **التقدير (جيد جداً، ممتاز، إلخ)** | `{{ Grade }}` |
| **دور التخرج الكلي (الأول/الثاني)** | `{{ attempt }}` |
| **رقم الأمر الجامعي** | `{{ order_number }}` |
| **تاريخ الأمر الجامعي** | `{{ order_date }}` |

---

## 2. مفاتيح التشغيل والمعلومات الاختيارية (Toggles & Options)
هذه المتغيرات تعتمد على التحديد من واجهة المستخدم (تفعيل/إلغاء تفعيل خيارات مثل التسلسل، التأجيل، التدريب الصيفي). يجب وضعها داخل شروط `{%p if Variable_ON %}` لتظهر فقط عند تفعيلها.

### أ. التدريب الصيفي
```text
{%p if Summer_ON %}
أكمل الطالب متطلبات التدريب الصيفي خلال العام الدراسي {{ Summer_Training_year }}.
{%p endif %}
```

### ب. التسلسل
```text
{%p if sequence_ON %}
تسلسل الطالب هو ({{ Sequence_of_Graduation }}) من أصل ({{ num_students }}) طالباً، وبمعدل للطالب الأول ({{ Average_of_First_Student }}).
{%p endif %}
```

### جـ. سنوات التأجيل والرسوب
```text
{%p if Failure_ON %}
سنوات التأجيل والرسوب:
{%p for year in failed_years %}
السنة {{ year.year_d }} / المرحلة {{ year.stage }} (سنة {{ year.state }})
{%p endfor %}
{%p endif %}
```

### د. العبور والدور الثاني
```text
{%p if Passed_ON %}
مواد الدور الثاني:
{%p for t_year in attempts %}
العام الدراسي: {{ t_year.year }} / المرحلة {{ t_year.stage }} ({{ t_year.subjects }})
{%p endfor %}
{%p endif %}
```

---

## 3. جداول الدرجات والمواد الدراسية (Course Tables)
يتم توليد الدرجات باستخدام دورة رئيسية `for pair` تمثل (العمود الأيمن والأيسر من الجدول) ودورة داخلية `for row` تمثل صفوف المواد الدراسية.

**الدورة الرئيسية للجداول:**
يمكن استخدام `{% for pair in paired_semesters %}` (للنظام الفصلي) أو `{% for pair in paired_years %}` (للنظام السنوي).

### متغيرات الـ Pair (العناوين والأدوار لكل عمود):
| الوصف (Description) | العمود الأيمن (Right Column) | العمود الأيسر (Left Column) |
| :--- | :--- | :--- |
| **العام الدراسي (مثل: 2022-2023)** | `{{ pair.year_right_label }}` | `{{ pair.year_left_label }}` |
| **المرحلة/الفصل (نص: المرحلة الأولى)** | `{{ pair.semester_right_label }}` | `{{ pair.semester_left_label }}` |
| **رقم المرحلة (رقم: 1, 2, ...)** | `{{ pair.num_s_r }}` | `{{ pair.num_s_l }}` |
| **الدور الخاص بهذا الفصل/المرحلة** | `{{ pair.attempt_right }}` | `{{ pair.attempt_left }}` |

### متغيرات الـ Row (المواد والدرجات):
توضع داخل جدول Word بين `{%tr for row in pair.rows %}` و `{%tr endfor %}`.

| الوصف (Description) | العمود الأيمن (Right Column) | العمود الأيسر (Left Column) |
| :--- | :--- | :--- |
| **اسم المادة** | `{{ row.right_subj }}` | `{{ row.left_subj }}` |
| **الدرجة** | `{{ row.right_mark }}` | `{{ row.left_mark }}` |
| **الوحدات** | `{{ row.right_unit }}` | `{{ row.left_unit }}` |

### مثال توضيحي لهيكل الجدول في Word:
```text
{% for pair in paired_semesters %}
[جدول يحتوي على العناوين: {{pair.year_right_label}} و {{pair.year_left_label}}]
{%tr for row in pair.rows %}
[صف الجدول يحتوي على الدرجات: {{row.right_subj}} و {{row.left_subj}} إلخ]
{%tr endfor %}
ناجح بالدور: {{pair.attempt_right}}        ناجح بالدور: {{pair.attempt_left}}
{% endfor %}
```

---

## 4. أسماء وتواقيع المسؤولين (Signatories)
في حال وجود تواقيع ديناميكية في نهاية الوثيقة:

```text
{%tr for s in signers %}
المنصب: {{ s.role }}
الاسم: {{ s.name }}
{%tr endfor %}
```
