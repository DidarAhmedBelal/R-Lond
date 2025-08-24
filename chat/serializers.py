import base64
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Message, Chat


class MessageSerializer(serializers.ModelSerializer):
    attachment = serializers.CharField(write_only=True, required=False, allow_blank=True)
    attachment_name = serializers.CharField(required=False, allow_blank=True)
    mime_type = serializers.CharField(required=False, allow_blank=True)
    message_type = serializers.CharField(read_only=True) 
    attachment_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'receiver', 'message', 'timestamp', 'reply_to',
            'attachment', 'attachment_name', 'mime_type', 'message_type',
            'attachment_url', 'is_read', 'is_deleted', 'is_edited', 'is_reported'
        ]
        read_only_fields = ['id', 'timestamp', 'sender', 'message_type']

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if instance.attachment and instance.attachment.path:
            try:
                with open(instance.attachment.path, 'rb') as file:
                    encoded_file = base64.b64encode(file.read()).decode('utf-8')
                    representation['attachment'] = f"{instance.mime_type},{encoded_file}"
            except FileNotFoundError:
                representation['attachment'] = None

        return representation

    def get_attachment_url(self, instance):
        request = self.context.get('request') if hasattr(self, 'context') else None
        if instance.attachment and hasattr(instance.attachment, 'url'):
            if request is not None:
                return request.build_absolute_uri(instance.attachment.url)
            return instance.attachment.url
        return None

    def to_internal_value(self, data):
        if 'attachment' in data and data['attachment']:
            try:
                file_data = data['attachment']

                if ',' in file_data:
                    mime_type, file_data = file_data.split(',', 1)
                    data['mime_type'] = mime_type.strip()

                decoded_file_data = base64.b64decode(file_data)

                attachment_name = data.get('attachment_name', 'attachment')
                file_name = f"{attachment_name}.file"

                content_file = ContentFile(decoded_file_data, name=file_name)
                data['attachment'] = content_file
            except Exception:
                raise serializers.ValidationError({'attachment': 'Invalid base64 format for file.'})

        return super().to_internal_value(data)


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['id', 'sender', 'receiver', 'created_at']
        read_only_fields = ['id', 'created_at', 'sender']
