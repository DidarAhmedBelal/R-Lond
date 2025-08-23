import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from user.models import User
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

            # Call the save and serialize method
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
                
        if 'username' not in notification_data:
            user = await self.get_user_info()
            notification_data['username'] = user.username

            if user.role == 'COMPANY' and hasattr(user, 'companyprofile'):
                notification_data['full_name'] = user.companyprofile.company_name
            elif user.role == 'AGENCY' and hasattr(user, 'agencyprofile'):
                notification_data['full_name'] = user.agencyprofile.agency_name
            else:
                notification_data['full_name'] = f"{user.first_name} {user.last_name}".strip() or None

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
        return User.objects.select_related('companyprofile', 'agencyprofile').get(id=self.user.id)

    def prepare_meta_data(self, message, base_meta_data=None):
        if base_meta_data and base_meta_data.get('type') == 'chat':
            meta_data = base_meta_data.copy()
            if meta_data.get('sender_id') and meta_data.get('receiver_id'):
                sender_id = int(meta_data['sender_id'])
                receiver_id = int(meta_data['receiver_id'])
                meta_data['chatroom_id'] = f'chat_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}'
            return meta_data

        meta_data = base_meta_data or {}
        message_upper = message.upper()
        if "MESSAGE" in message_upper or "CHAT" in message_upper:
            meta_data['type'] = 'chat'
            import re

            meta_data['chat_type'] = 'direct'

        elif "BID" in message_upper:
            meta_data['type'] = 'bid'
            if base_meta_data and 'bid_id' in base_meta_data:
                meta_data['bid_id'] = base_meta_data['bid_id']
                meta_data['project_id'] = base_meta_data.get('project_id')
                meta_data['bid_status'] = base_meta_data.get('bid_status')

        elif "OFFER" in message_upper:
            meta_data['type'] = 'offer'
            if base_meta_data:
                meta_data['offer_id'] = base_meta_data.get('offer_id')
                meta_data['project_id'] = base_meta_data.get('project_id')
                meta_data['offer_status'] = base_meta_data.get('offer_status')

        elif "ORDER" in message_upper:
            meta_data['type'] = 'order'
            if base_meta_data:
                meta_data['order_id'] = base_meta_data.get('order_id')
                meta_data['order_status'] = base_meta_data.get('order_status')
                meta_data['project_id'] = base_meta_data.get('project_id')

        elif "PROJECT" in message_upper:
            meta_data['type'] = 'project'
            if base_meta_data:
                meta_data['project_id'] = base_meta_data.get('project_id')
                meta_data['project_status'] = base_meta_data.get('project_status')
                meta_data['project_type'] = base_meta_data.get('project_type')

        elif "AGENCY" in message_upper:
            meta_data['type'] = 'agency_profile'
            if base_meta_data:
                meta_data['agency_id'] = base_meta_data.get('agency_id')

        elif "COMPANY" in message_upper:
            meta_data['type'] = 'company_profile'
            if base_meta_data:
                meta_data['company_id'] = base_meta_data.get('company_id')

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

        notification = Notification.objects.select_related(
            'user',
            'user__companyprofile',
            'user__agencyprofile'
        ).get(id=notification.id)

        serializer = NotificationSerializer(notification)
        return serializer.data
