"""
Views for student CRUD operations.
"""

from apps.students.forms import StudentForm
from apps.students.models import Student
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class StudentListView(LoginRequiredMixin, ListView):
    """List of all students for the current user."""

    model = Student
    template_name = "students/student_list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class StudentDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a student."""

    model = Student
    template_name = "students/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class StudentCreateView(LoginRequiredMixin, CreateView):
    """Create a new student."""

    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, _("Student successfully created."))
        return super().form_valid(form)


class StudentUpdateView(LoginRequiredMixin, UpdateView):
    """Update a student."""

    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:list")

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Student successfully updated."))
        return super().form_valid(form)


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a student."""

    model = Student
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("students:list")

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Student successfully deleted."))
        return super().delete(request, *args, **kwargs)
