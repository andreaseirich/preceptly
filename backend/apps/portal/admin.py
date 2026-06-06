from django.contrib import admin

from apps.portal.models import (
    ParentStudentLink,
    PortalMessage,
    PortalUser,
    ProgressNote,
    StudentPortalLink,
)

admin.site.register(PortalUser)
admin.site.register(StudentPortalLink)
admin.site.register(ParentStudentLink)
admin.site.register(ProgressNote)
admin.site.register(PortalMessage)
