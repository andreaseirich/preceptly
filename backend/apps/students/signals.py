import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.students.models import StudentDocument

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=StudentDocument)
def delete_student_document_file(sender, instance, **kwargs):
    """Physische Datei löschen, wenn das Dokument-Objekt entfernt wird."""
    if instance.file and instance.file.name:
        try:
            instance.file.delete(save=False)
        except Exception:
            logger.warning(
                "Datei nicht löschbar (vermutlich nicht vorhanden): %s", instance.file.name
            )
