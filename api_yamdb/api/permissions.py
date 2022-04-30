from rest_framework import permissions
from reviews.models import UserRole


class AdminModifyOrReadOnlyPermission(permissions.BasePermission):
    """
    Только у адина есть доступ для
    редактирования или только для получения данных.
    """
    def has_permission(self, request, view):
        return (request.method in permissions.SAFE_METHODS
                or request.user.is_authenticated)
    


class UserPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if view.action in ['get_me', 'update_me', 'delete_me']:
            return request.user.is_authenticated
        return (
            request.user.is_authenticated
            and request.user.role == UserRole.ADMIN
        )

    def has_object_permission(self, request, view, obj):
        if view.action in ['get_me', 'update_me', 'delete_me']:
            return obj.author == request.user
        return (
            request.user.is_authenticated
            and request.user.role == UserRole.ADMIN
        )


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_authenticated:
            return bool(request.user.is_staff or request.user.role == UserRole.ADMIN)


class ReviewAndComment(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method == 'POST' or view.action == 'create':
            return not request.user.is_anonymous()

        if request.method in ('PATCH', 'DELETE'):
            return (request.user == obj.author
                    or request.user.role == UserRole.ADMIN
                    or request.user.role == UserRole.MODERATOR)

        if request.method in permissions.SAFE_METHODS:
            return True
        return False
