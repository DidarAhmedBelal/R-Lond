# views.py
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import DestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from user.models import User
from .models import Notification
from .serializers import NotificationSerializer
from .utils import send_notification_to_user
from rest_framework.exceptions import PermissionDenied


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    """
    GET /notifications/
    Returns all notifications for the current user.
    """
    qs = request.user.notifications.all().select_related(
        'user',
        'user__companyprofile',
        'user__agencyprofile'
    ).order_by('-event_time')
    serializer = NotificationSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unseen_notification_list(request):
    """
    GET /notifications/unseen/
    Returns only unseen notifications for the current user.
    """
    qs = request.user.notifications.filter(seen=False).select_related(
        'user',
        'user__companyprofile',
        'user__agencyprofile'
    ).order_by('-event_time')
    serializer = NotificationSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_seen(request, pk):
    """
    POST /notifications/<pk>/seen/
    Marks the given notification (must belong to current user) as seen.
    Returns the updated notification.
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.seen:
        notification.seen = True
        notification.save(update_fields=['seen'])
    serializer = NotificationSerializer(notification)
    return Response(serializer.data)

class NotificationDeleteAPIView(DestroyAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Swagger schema generation time protection
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()

        user = self.request.user
        if not hasattr(user, 'notifications'):
            raise PermissionDenied("User has no notifications attribute.")

        return user.notifications.all()


@api_view(['GET'])
@permission_classes([AllowAny])
def hit_notify(request, email):
    user = get_object_or_404(User, email=email)
    send_notification_to_user(user, f"hello {email}")
    return JsonResponse({"message": "notification sent"})
