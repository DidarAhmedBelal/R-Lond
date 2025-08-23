from rest_framework import serializers
from .models import Notification
from users.models import User  
from users.serializers import UserSerializer  
from users.enums import UserRole  


class NotificationSerializer(serializers.ModelSerializer):
    sender = serializers.CharField(source='user.username', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    meta_data = serializers.JSONField(required=False)

    class Meta:
        model = Notification
        fields = [
            'id',
            'sender',
            'event_time',
            'message',
            'seen',
            'username',
            'full_name',
            'meta_data',
        ]
        read_only_fields = ['id', 'event_time']

    def get_full_name(self, obj):

        if not obj.user:
            return None

        if obj.user.role == UserRole.VENDOR.value:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

        elif obj.user.role == UserRole.CUSTOMER.value:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

        elif obj.user.role == UserRole.ADMIN.value:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or "Admin"

        return obj.user.username
