"""
Forms für Student-Model.
"""

from django import forms

from apps.students.models import Student


class StudentForm(forms.ModelForm):
    """Form für Student-Erstellung und -Bearbeitung."""

    class Meta:
        model = Student
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "school",
            "grade",
            "subjects",
            "notes",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "school": forms.TextInput(attrs={"class": "form-control"}),
            "grade": forms.TextInput(attrs={"class": "form-control"}),
            "subjects": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
