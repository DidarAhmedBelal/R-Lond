import datetime
from django.conf import settings
from django.db import models
from django.db.models import Q, Case, When, F, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from users.models import User
from .models import Message, Chat
from .serializers import MessageSerializer, ChatSerializer

from notification.utils import send_notification_to_user


class ChatMessagesListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List chat messages with a user",
        operation_description="Returns all non-deleted messages between the authenticated user and the user with the given ID (pk)."
    )
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', None):
            return Message.objects.none()

        pk = self.kwargs.get('pk')
        get_object_or_404(User, pk=pk)

        return Message.objects.filter(
            Q(sender=self.request.user, receiver_id=pk) |
            Q(sender_id=pk, receiver=self.request.user),
            is_deleted=False
        ).select_related('sender', 'receiver').order_by('timestamp')


class UserChatsListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List all chat users for authenticated user",
        operation_description="Returns all users the authenticated user has had a chat with, along with their basic info."
    )
    def get(self, request, *args, **kwargs):
        qs = Chat.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user)
        ).order_by('-created_at').annotate(
            user_id=Case(
                When(sender_id=request.user.id, then=F('receiver_id')),
                default=F('sender_id'),
                output_field=models.IntegerField(),
            ),
            user_email=Case(
                When(sender_id=request.user.id, then=F('receiver__email')),
                default=F('sender__email'),
                output_field=models.CharField(),
            ),
            username=Case(
                When(sender_id=request.user.id, then=F('receiver__username')),
                default=F('sender__username'),
                output_field=models.CharField(),
            ),
            agency_name=Case(
                When(sender_id=request.user.id, then=F('receiver__agencyprofile__agency_name')),
                default=F('sender__agencyprofile__agency_name'),
                output_field=models.CharField(),
            ),
            company_name=Case(
                When(sender_id=request.user.id, then=F('receiver__companyprofile__company_name')),
                default=F('sender__companyprofile__company_name'),
                output_field=models.CharField(),
            ),
            user_image=Case(
                When(
                    sender_id=request.user.id,
                    receiver__image__isnull=False,
                    receiver__image__gt='',
                    then=F('receiver__image'),
                ),
                When(
                    receiver_id=request.user.id,
                    sender__image__isnull=False,
                    sender__image__gt='',
                    then=F('sender__image'),
                ),
                default=Value(None),
                output_field=models.CharField(),
            )
        )

        data = [
            {
                "user_email": chat.user_email,
                "username": chat.username,
                "id": chat.user_id,
                # "full_name": chat.agency_name or chat.company_name or chat.username or chat.user_email.split('@')[0],
                "user_image": f"{settings.MEDIA_URL}{chat.user_image}" if chat.user_image else None,
                "name": chat.agency_name or chat.company_name or chat.username or chat.user_email.split('@')[0]
            } for chat in qs
        ]

        return Response(data, status=status.HTTP_200_OK)


class MessageDeleteView(generics.DestroyAPIView):
    queryset = Message.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Delete a message",
        operation_description="Deletes a message (soft delete) if the authenticated user is the sender."
    )
    def get_object(self):
        obj = get_object_or_404(Message, pk=self.kwargs.get('pk'), is_deleted=False)
        if obj.sender != self.request.user:
            raise PermissionDenied("You do not have permission to delete this message.")
        return obj

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"detail": "Message deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class MessageUpdateView(generics.UpdateAPIView):
    queryset = Message.objects.select_related('sender').all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['patch']

    @swagger_auto_schema(
        operation_summary="Update a message",
        operation_description="Edits the content of a message sent by the authenticated user."
    )
    def get_object(self):
        obj = get_object_or_404(Message, pk=self.kwargs.get('pk'), is_deleted=False)
        if obj.sender != self.request.user:
            raise PermissionDenied("You do not have permission to edit this message.")
        return obj

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['message'],
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        operation_summary="Update message content"
    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_content = request.data.get('message')

        if not new_content:
            return Response({"detail": "field 'message' is required"}, status=status.HTTP_400_BAD_REQUEST)

        instance.message = new_content
        instance.is_edited = True
        instance.save()

        return Response({"detail": "Message edited successfully."}, status=status.HTTP_200_OK)


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List all messages with a user",
        operation_description="Returns all messages between authenticated user and the specified user ID."
    )
    def get_queryset(self):
        user_id = self.kwargs.get('pk')
        get_object_or_404(User, pk=user_id)
        return Message.objects.filter(
            Q(sender=self.request.user, receiver_id=user_id) |
            Q(sender_id=user_id, receiver=self.request.user),
            is_deleted=False
        ).select_related('sender', 'receiver').order_by('timestamp')

    @swagger_auto_schema(
        operation_summary="Send a message to a user",
        operation_description="Creates and sends a message to the user specified by pk.",
    )
    def perform_create(self, serializer):
        receiver_id = self.kwargs.get('pk')
        receiver = get_object_or_404(User, pk=receiver_id)
        serializer.save(sender=self.request.user, receiver=receiver)
