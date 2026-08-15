# =============================================================================
# utils/error_formatter.py — Smart Error Formatter for User Notifications
# =============================================================================

import re
import json

def format_error_message(err: Exception | str) -> tuple[str, str]:
    """
    Parses raw exceptions, API JSON detail responses, MySQL trigger error codes,
    and HTTP errors into clean, human-readable bilingual notification messages.

    Returns:
        tuple[str, str]: (Title, Detail Description)
    """
    raw_str = str(err or "").strip()
    if not raw_str:
        return ("خطأ / Error", "حدث خطأ غير متوقع / An unexpected error occurred.")

    # Extract JSON detail payload if present
    json_detail = None
    json_match = re.search(r"\{.*\}", raw_str, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if isinstance(data, dict) and "detail" in data:
                json_detail = data["detail"]
        except Exception:
            pass

    if json_detail:
        if isinstance(json_detail, list) and len(json_detail) > 0 and isinstance(json_detail[0], dict):
            field = json_detail[0].get("loc", [])[-1] if json_detail[0].get("loc") else ""
            msg_txt = json_detail[0].get("msg", "")
            msg = f"الحقل المطلوب مفقود ({field}): {msg_txt}" if field else msg_txt
        else:
            msg = str(json_detail)
    else:
        msg = raw_str

    # 1. MySQL Trigger Error 1644: Signatory Slot Conflict
    if "1644" in msg or "This signatory slot is already assigned" in msg:
        return (
            "تعارض في موقع التوقيع — Signatory Slot Conflict",
            "عذراً، موقع التوقيع هذا مخصص لشخص آخر بالفعل. يرجى اختيار ترتيب آخر أو إزالة التوقيع السابق أولاً."
        )

    # 2. MySQL Error 1062: Duplicate Entry
    if "1062" in msg or "Duplicate entry" in msg:
        dup_match = re.search(r"Duplicate entry '([^']+)' for key '([^']+)'", msg)
        if dup_match:
            val, key = dup_match.groups()
            return (
                "سجل مكرر — Duplicate Entry",
                f"القيمة '{val}' مستخدمة بالفعل في النظام ({key}). يرجى اختيار قيمة مختلفة."
            )
        return (
            "سجل مكرر — Duplicate Entry",
            "عذراً، هذا السجل أو اسم المستخدم موجود بالفعل في النظام."
        )

    # 3. Foreign Key Constraint Violation (Error 1451 / 1452)
    if "1451" in msg or "1452" in msg or "foreign key constraint" in msg.lower():
        return (
            "تعارض في البيانات المرتبطة — Linked Data Constraint",
            "لا يمكن إتمام العملية لوجود سجلات أو بيانات أخرى مرتبطة بهذا العنصر في النظام."
        )

    # 4. Operation Denied
    if "Operation Denied:" in msg:
        denied_msg = msg.split("Operation Denied:")[-1].strip().strip('"}')
        return (
            "تم رفض العملية — Operation Denied",
            denied_msg
        )

    # 5. Missing / Required Field Validation
    if "Field required" in msg or "missing" in msg.lower():
        return (
            "بيانات غير مكتملة — Missing Information",
            "يرجى التأكد من ملء جميع الحقول المطلوبة بشكل صحيح قبل الحفظ."
        )

    # 6. General API & Network Errors Cleaning
    clean_msg = re.sub(
        r"^(API update failed:|API insert failed:|HTTPConnectionPool|500 Internal Server Error:)",
        "",
        msg
    ).strip()
    clean_msg = re.sub(r"^\d{3,4}\s*\(\d+\):\s*", "", clean_msg).strip()
    clean_msg = clean_msg.strip('"{}\'')

    if len(clean_msg) > 160:
        clean_msg = clean_msg[:160] + "..."

    return ("تنبيه — Notice", clean_msg or "تعذر إتمام العملية. يرجى المحاولة مرة أخرى.")
