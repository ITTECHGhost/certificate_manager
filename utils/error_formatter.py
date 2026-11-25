# =============================================================================
# utils/error_formatter.py — Smart Error Formatter for User Notifications
# =============================================================================

import re
import json
from collections import deque
from datetime import datetime

# The last raw errors shown to the user (before translation). The feedback dialog sends
# them to IT, so a friendly toast in a screenshot never hides the real cause.
recent_errors: deque = deque(maxlen=5)


def remember_error(raw) -> None:
    text = str(raw or "").strip()
    if text:
        recent_errors.append(f"{datetime.now():%Y-%m-%d %H:%M:%S} {text[:600]}")


def _mysql_code(msg: str, *codes: str) -> bool:
    """True only for a real MySQL error code, e.g. '1452 (23000)' - not any number that contains it."""
    return any(re.search(rf"(?<!\d){c}(?!\d)\s*\(\w{{5}}\)", msg) for c in codes)


def format_error_message(err: Exception | str) -> tuple[str, str]:
    """
    Parses raw exceptions, API JSON detail responses, MySQL trigger error codes,
    and HTTP errors into clean, human-readable Arabic notification messages.

    Returns:
        tuple[str, str]: (Title, Detail Description)
    """
    raw_str = str(err or "").strip()
    if not raw_str:
        return ("خطأ", "حدث خطأ غير متوقع. حاول مرة أخرى.")

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
    if _mysql_code(msg, "1644") or "This signatory slot is already assigned" in msg:
        return (
            "تعارض في موقع التوقيع",
            "عذراً، موقع التوقيع هذا مخصص لشخص آخر بالفعل. يرجى اختيار ترتيب آخر أو إزالة التوقيع السابق أولاً."
        )

    # 2. MySQL Error 1062: Duplicate Entry
    if _mysql_code(msg, "1062") or "Duplicate entry" in msg:
        dup_match = re.search(r"Duplicate entry '([^']+)' for key '([^']+)'", msg)
        if dup_match:
            val, key = dup_match.groups()
            return (
                "سجل مكرر",
                f"القيمة '{val}' مستخدمة بالفعل في النظام ({key}). يرجى اختيار قيمة مختلفة."
            )
        return (
            "سجل مكرر",
            "عذراً، هذا السجل أو اسم المستخدم موجود بالفعل في النظام."
        )

    # 3. Foreign Key Constraint Violation (Error 1451 / 1452)
    # 1452 = adding a row that points to a record the server does not have (e.g. a student
    # deleted / re-imported on the server while this screen still holds the old id).
    if _mysql_code(msg, "1452") or "Cannot add or update a child row" in msg:
        return (
            "السجل المرتبط غير موجود على الخادم",
            "الطالب أو السجل المرتبط لم يعد موجوداً على الخادم (ربما حُذف أو أُعيد استيراده). "
            "أعد اختيار الطالب من البحث ثم حاول مرة أخرى."
        )
    if _mysql_code(msg, "1451") or "foreign key constraint" in msg.lower():
        return (
            "تعارض في البيانات المرتبطة",
            "لا يمكن إتمام العملية لوجود سجلات أو بيانات أخرى مرتبطة بهذا العنصر في النظام."
        )

    # 4. Operation Denied
    if "Operation Denied:" in msg:
        denied_msg = msg.split("Operation Denied:")[-1].strip().strip('"}')
        return (
            "تم رفض العملية",
            denied_msg
        )

    # 5. Missing / Required Field Validation
    if "Field required" in msg or "missing" in msg.lower():
        return (
            "بيانات غير مكتملة",
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

    return ("تنبيه", clean_msg or "تعذر إتمام العملية. يرجى المحاولة مرة أخرى.")
