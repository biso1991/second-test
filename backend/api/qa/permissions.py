from rest_framework import permissions
from api.qa.models import File, Model, Project, Training_Job, Training_Job_Monitoring


class Has_permissionOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, views, obj):
        # Single object permissions
        if isinstance(obj, Project):
            return obj.owner.id == request.user.id
        elif isinstance(obj, File):
            return obj.project_f.owner.id == request.user.id
        elif isinstance(obj, Training_Job):
            return obj.project.owner.id == request.user.id
        elif isinstance(obj, Training_Job_Monitoring):
            return obj.training_job.project.owner.id == request.user.id
        elif isinstance(obj, Model):
            return obj.owner.id == request.user.id
        else:
            return False
