import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from users.models import User
from .models import Notification
from .serializers import NotificationSerializer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        if not isinstance(self.scope['user'], User):
            await self.send_json({"error": self.scope.get('error', 'Unauthorized')}, close=True)
            return

        self.user = self.scope['user']
        self.notification_userid = str(self.user.id)
        self.room_group_name = f'notifications_{self.notification_userid}'
        print(f"Connecting to group: {self.room_group_name}")

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

    async def disconnect(self, close_code):
        if isinstance(self.scope['user'], User):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        message_type = content.get("type")
        if message_type == "send_notification":
            notification_data = content.get("notification")
            if not notification_data:
                await self.send_json({"error": "No notification data provided"})
                return

            notification_data = await self.save_and_serialize_notification(notification_data)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "send_notification",
                    "notification": notification_data
                }
            )

    async def send_notification(self, event):
        notification_data = event.get('notification', {})

        if 'email' not in notification_data:
            notification_data['email'] = self.user.email

        if 'full_name' not in notification_data:
            notification_data['full_name'] = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.email

        meta_data = notification_data.get('meta_data', {})

        if not meta_data and "New message from" in notification_data.get('message', ''):
            meta_data = {'type': 'chat'}
            notification_data['meta_data'] = meta_data

        await self.send_json({
            'type': 'notification',
            'data': notification_data,
        })

    @database_sync_to_async
    def get_user_info(self):
        return User.objects.get(id=self.user.id)

    def prepare_meta_data(self, message, base_meta_data=None):
        meta_data = base_meta_data or {}
        message_upper = message.upper()

        if "MESSAGE" in message_upper or "CHAT" in message_upper:
            meta_data['type'] = 'chat'
            meta_data['chat_type'] = 'direct'
        elif "ORDER" in message_upper:
            meta_data['type'] = 'order'
            if base_meta_data:
                meta_data['order_id'] = base_meta_data.get('order_id')
                meta_data['order_status'] = base_meta_data.get('order_status')
        else:
            meta_data['type'] = 'general'

        return meta_data

    @database_sync_to_async
    def save_and_serialize_notification(self, data):
        message = data.get("message", "")
        meta_data = self.prepare_meta_data(message, data.get("meta_data", {}))

        notification = Notification.objects.create(
            user=self.user,
            message=message,
            seen=data.get("seen", False),
            meta_data=meta_data
        )

        serializer = NotificationSerializer(notification)
        return serializer.data
