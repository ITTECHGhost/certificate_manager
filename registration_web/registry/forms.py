from django import forms

from .models import Student

# Field order = order of the paper registration form (to be matched to the real form).
PAPER_ORDER = [
    "name_ar", "name_en", "mother_name", "birth_date", "birth_place", "gender",
    "national_id", "phone", "address",
    "school_name", "graduation_year", "average",
    "department", "study_type",
]


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = PAPER_ORDER
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}
