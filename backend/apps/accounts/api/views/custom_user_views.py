# /home/ram/aparsoft/backend/apps/accounts/api/views/custom_user_views.py

"""
ViewSets for accounts app models.
Provides RESTful API endpoints for user accounts and related models.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from django.db import models

from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend

from accounts.models.custom_user import CustomUser, UserContact


from ..serializers.custom_user_serializers import (
    CustomUserSerializer,
    CustomUserMinimalSerializer,
    UserContactSerializer,
    UserContactMinimalSerializer,
)

User = get_user_model()


class CustomUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CustomUser model.
    Provides CRUD operations and additional actions for user management.
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'role_status',
                        'is_active', 'subscription_tier', 'email_verified']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['date_joined', 'last_active', 'username', 'email']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CustomUserMinimalSerializer
        return CustomUserSerializer

    def get_queryset(self):
        """Filter queryset based on user role and permissions."""
        user = self.request.user
        queryset = CustomUser.objects.all()

        # Admin users can see all users
        if user.is_staff or user.is_superuser:
            return queryset

        # Project managers can see team members and clients
        if user.is_project_manager:
            return queryset.filter(
                models.Q(assigned_projects__in=user.assigned_projects.all()) |
                models.Q(id=user.id)
            ).distinct()

        # Account managers can see their assigned clients
        if user.is_account_manager and hasattr(user, 'account_manager_profile'):
            client_ids = user.account_manager_profile.clients.values_list(
                'user_id', flat=True)
            return queryset.filter(
                models.Q(id__in=client_ids) |
                models.Q(id=user.id)
            )

        # Regular users can only see themselves
        return queryset.filter(id=user.id)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get the authenticated user's profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def verify_email(self, request, pk=None):
        """Verify user's email address."""
        user = self.get_object()
        user.verify_email()
        return Response({'message': 'Email verified successfully'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def get_assigned_projects(self, request, pk=None):
        """Get projects assigned to the user."""
        user = self.get_object()
        projects = user.get_assigned_projects()

        # Using a project serializer (not defined here)
        from workitems.api.serializers import ProjectMinimalSerializer
        serialized_projects = [
            {
                'project': ProjectMinimalSerializer(item['project']).data,
                'role': item['role'],
                'status': item['status'],
                'tasks_count': item['tasks_count'],
                'completed_tasks': item['completed_tasks']
            }
            for item in projects
        ]

        return Response(serialized_projects)

    @action(detail=True, methods=['post'])
    def update_subscription(self, request, pk=None):
        """Update user's subscription tier."""
        user = self.get_object()
        new_tier = request.data.get('subscription_tier')
        reason = request.data.get('reason')

        if not new_tier:
            return Response(
                {'error': 'Subscription tier is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user.update_subscription(new_tier, reason)
            return Response(
                {'message': f'Subscription updated to {new_tier}'},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def profile_image(self, request):
        """Get current user's profile image URL - compatibility endpoint."""
        from ..views.profile_avatar_views import ProfileAvatarView
        avatar_view = ProfileAvatarView()
        avatar_view.request = request
        return avatar_view.get(request)


class UserContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserContact model.
    Provides CRUD operations for user contact information.
    """
    queryset = UserContact.objects.all()
    serializer_class = UserContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return UserContactMinimalSerializer
        return UserContactSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user

        # Admin users can see all contacts
        if user.is_staff or user.is_superuser:
            return UserContact.objects.all()

        # Regular users can only see their own contact
        return UserContact.objects.filter(user=user)
