from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.students.models import StudentDocument


@receiver(post_delete, sender=StudentDocument)
def delete_student_document_file(sender, instance, **kwargs):
    """Physische Datei löschen, wenn das Dokument-Objekt entfernt wird."""
    if instance.file and instance.file.name:
        try:
            instance.file.delete(save=False)
        except Exception:
            pass  # Datei bereits nicht mehr vorhanden
