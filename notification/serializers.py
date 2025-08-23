# serializers.py

from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    sender = serializers.CharField(source='user.username', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    meta_data = serializers.JSONField(required=False)

    class Meta:
        model = Notification
        fields = ['id', 'sender', 'event_time', 'message', 'seen', 'username', 'full_name', 'meta_data']
        read_only_fields = ['id', 'event_time']

    def get_full_name(self, obj):
        if obj.user.role == 'COMPANY' and hasattr(obj.user, 'companyprofile'):
            return obj.user.companyprofile.company_name
        elif obj.user.role == 'AGENCY' and hasattr(obj.user, 'agencyprofile'):
            return obj.user.agencyprofile.agency_name
        elif obj.user.first_name or obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return None

    
