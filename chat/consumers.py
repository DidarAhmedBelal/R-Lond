import base64
import json
import uuid
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.files.base import ContentFile
from django.db.models import Q
from twisted.pair.ip import MAX_SIZE
from user.models import User as CustomUser
from .models import Message, Chat
from .serializers import MessageSerializer
from notification.models import Notification

SERIALIZE_MESSAGE = sync_to_async(MessageSerializer.data.fget)

@sync_to_async
def create_notification(user, sender_name, message_text, meta_data=None):
    return Notification.objects.create(
        user=user,
        message=f"New message from {sender_name}: {message_text[:50]}...",
        meta_data=meta_data
    )

def filesize_from_base64(b64_str: str) -> int:
    b64_str = "".join(b64_str.split())
    padding = b64_str.count("=")
    return (len(b64_str) * 3) // 4 - padding


class ChatConsumer(AsyncJsonWebsocketConsumer):
    MAX_ATTACHMENT_SIZE = Message.MAX_FILE_SIZE

    async def connect(self):
        await self.accept()

        if not isinstance(self.scope['user'], CustomUser):
            await self.send(json.dumps({'error': self.scope['error']}))
            await self.close()
            return

        self.user = self.scope['user']
        self.first_message = True

        get_user_chats = sync_to_async(lambda: list(
            Chat.objects.filter(
                Q(sender=self.user) | Q(receiver=self.user)
            ).values_list('sender_id', 'receiver_id')
        ))
        
        user_chats = await get_user_chats()

        for sender_id, receiver_id in user_chats:
            users = sorted([sender_id, receiver_id])
            room_id = f"chat_{users[0]}_{users[1]}"
            await self.channel_layer.group_add(room_id, self.channel_name)

            if not hasattr(self, 'room_ids'):
                self.room_ids = set()
            self.room_ids.add(room_id)

        await self.send_json({
            "success": f"user {self.user.email} is subscribed for chat",
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'room_ids'):
            for room_id in self.room_ids:
                await self.channel_layer.group_discard(
                    room_id,
                    self.channel_name
                )

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if not text_data:
            await self.send_json({'error': 'no text section for incoming WebSocket frame!'})
            return
        try:
            await self.receive_json(await self.decode_json(text_data), **kwargs)
        except json.decoder.JSONDecodeError as e:
            await self.send_json({"error": f"json_decode_error: {str(e)}"})
            return

    async def receive_json(self, message_dict, **kwargs):
        if 'error' in message_dict:
            await self.send_json(message_dict)
            return

        user_id = message_dict.get("user_id")
        message = message_dict.get("message")
        attachment = message_dict.get("attachment_data")
        mime_type = message_dict.get("mime_type")
        file_name = message_dict.get("attachment_name")
        reply_to = message_dict.get("reply_to") or None
        delete_id = message_dict.get("delete_id")

        if delete_id:
            message_obj = await Message.objects.select_related('sender', 'receiver').filter(id=delete_id).afirst()
            if message_obj.sender != self.user:
                return await self.send_json({"error": "You do not have permission to delete this message."})
            message_obj.is_deleted = True
            await message_obj.asave()

            room_users = sorted([message_obj.sender.id, message_obj.receiver.id])
            room_id = f"chat_{room_users[0]}_{room_users[1]}"
            await self.channel_layer.group_send(
                room_id,
                {
                    "type": "send_message",
                    "message": {
                        "event": {
                            'name': 'delete',
                            'delete_id': message_obj.id
                        },
                        'room_id': room_id 
                    },
                }
            )

            receiver = message_obj.receiver
            meta_data = {
                'type': 'chat',
                'sender_id': str(self.user.id),
                'receiver_id': str(receiver.id),
                'chatroom_id': room_id,
                'chat_type': 'direct'
            }
            notification = await create_notification(
                receiver,
                self.user.get_full_name() or self.user.email,
                f"A message was deleted in your chat.",
                meta_data
            )
            await self.channel_layer.group_send(
                f'notifications_{receiver.id}',
                {
                    'type': 'send_notification',
                    'notification': {
                        'id': str(notification.id),
                        'message': notification.message,
                        'event_time': notification.event_time.isoformat(),
                        'seen': notification.seen,
                        'meta_data': meta_data
                    }
                }
            )
            return

        if user_id is None:
            return await self.send_json({'error': 'user_id is required'})

        if str(user_id) == str(self.user.id):
            return await self.send_json({'error': "can't send message to self"})

        try:
            receiver = await CustomUser.objects.aget(id=user_id)
        except CustomUser.DoesNotExist:
            return await self.send_json({'error': f'user {user_id} not found'})

        if attachment and not file_name:
            return await self.send_json({'error': 'attachment_name is required'})

        if attachment and filesize_from_base64(attachment) > self.MAX_ATTACHMENT_SIZE:
            return await self.send_json({'error': f'file size is too large > {self.MAX_ATTACHMENT_SIZE}'})

        if not attachment and not message:
            return await self.send_json({'error': 'message is required'})


        users = sorted([self.user.id, receiver.id])
        room_id = f"chat_{users[0]}_{users[1]}"

        if self.first_message:
            try:
                await Chat.objects.aget(
                    Q(sender=self.user, receiver=receiver) |
                    Q(sender=receiver, receiver=self.user)
                )
            except Chat.DoesNotExist:
                await Chat.objects.acreate(sender=self.user, receiver=receiver)
            self.first_message = False

        if reply_to:
            try:
                reply_to_obj = await Message.objects.aget(
                    Q(sender=receiver, receiver=self.user, id=reply_to) |
                    Q(sender=self.user, receiver=receiver, id=reply_to)
                )

                if reply_to_obj.sender != self.user:
                    users = sorted([self.user.id, reply_to_obj.sender.id])
                    reply_room_id = f"chat_{users[0]}_{users[1]}"
                    meta_data = {
                        'type': 'chat',
                        'sender_id': str(self.user.id),
                        'receiver_id': str(reply_to_obj.sender.id),
                        'chatroom_id': reply_room_id,
                    }
                    notification = await create_notification(
                        reply_to_obj.sender,
                        self.user.get_full_name() or self.user.email,
                        f"replied to your message: {reply_to_obj.message[:50]}",
                        meta_data
                    )
                    await self.channel_layer.group_send(
                        f'notifications_{reply_to_obj.sender.id}',
                        {
                            'type': 'send_notification',
                            'notification': {
                                'id': str(notification.id),
                                'message': notification.message,
                                'event_time': notification.event_time.isoformat(),
                                'seen': notification.seen,
                                'meta_data': meta_data
                            }
                        }
                    )
                reply_to = reply_to_obj
            except Message.DoesNotExist:
                return await self.send_json({
                    'error': f"can't reply to message_id {reply_to} as it is not found or doesn't belong to this chat"
                })

        message_obj = Message(
            sender=self.user,
            message=message,
            receiver=receiver,
            reply_to=reply_to,
            attachment_name=file_name,
            message_type='sent'
        )

        if attachment:
            try:
                mime_type, atch_data = attachment.split(',')
                file_data = base64.b64decode(atch_data)
                message_obj.mime_type = mime_type
                await sync_to_async(message_obj.attachment.save)(
                    f"{str(uuid.uuid1())}_{file_name}", ContentFile(file_data))
            except Exception as e:
                return await self.send_json({'error': f'attachment decoding error: {str(e)}'})

        await message_obj.asave()

        message_serializer = MessageSerializer(message_obj)
        message_data = await SERIALIZE_MESSAGE(message_serializer)
        message_data['message_type'] = 'sent'
        message_data['room_id'] = room_id

        meta_data = {
            'type': 'chat',
            'sender_id': str(self.user.id),
            'receiver_id': str(receiver.id),
            'chatroom_id': room_id,
            'chat_type': 'direct'
        }
        notification = await create_notification(receiver, self.user.get_full_name() or self.user.email, message, meta_data)

        await self.channel_layer.group_send(
            f'notifications_{receiver.id}',
            {
                'type': 'send_notification',
                'notification': {
                    'id': str(notification.id),
                    'message': notification.message,
                    'event_time': notification.event_time.isoformat(),
                    'seen': notification.seen,
                    'meta_data': meta_data
                }
            }
        )

        await self.channel_layer.group_send(
            room_id,
            {
                "type": "send_message",
                "message": message_data,
            }
        )

    async def send_message(self, event):
        message = event["message"]

        if not message.get('event'):
            if message.get('sender') and str(message['sender']) == str(self.user.id):
                message['message_type'] = 'sent'
            else:
                message['message_type'] = 'received'

            if message.get('sender') and message.get('receiver'):
                users = sorted([int(message['sender']), int(message['receiver'])])
                message['room_id'] = f"chat_{users[0]}_{users[1]}"
        
        await self.send_json({"message": message})
