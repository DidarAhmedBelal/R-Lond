# utils.py

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from users.models import User
from notification.models import Notification


def prepare_notification_meta_data(message, sender=None, base_meta_data=None):

    meta_data = base_meta_data or {}
    message_upper = message.upper()

    if sender:
        meta_data['sender_id'] = str(sender.id)
        meta_data['sender_email'] = sender.email
        meta_data['sender_name'] = f"{sender.first_name} {sender.last_name}".strip() or sender.email

    if "CHAT" in message_upper or "MESSAGE" in message_upper:
        meta_data['type'] = 'chat'
    elif "ORDER" in message_upper:
        meta_data['type'] = 'order'
    else:
        meta_data['type'] = 'general'

    return meta_data


def send_notification_to_user(user, message, sender=None, meta_data=None):

    assert isinstance(user, User)
    if sender:
        assert isinstance(sender, User)

    channel_layer = get_channel_layer()
    notification_meta_data = prepare_notification_meta_data(message, sender, meta_data)

    notification = Notification.objects.create(
        user=user,
        sender=sender,
        message=message,
        meta_data=notification_meta_data
    )

    full_name = f"{user.first_name} {user.last_name}".strip() or user.email

    if user and user.is_active:
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'send_notification',
                'notification': {
                    "id": notification.id,
                    "message": message,
                    "time": notification.created_at.isoformat(),
                    "seen": False,
                    "email": user.email,
                    "full_name": full_name,
                    "meta_data": notification.meta_data,
                },
            }
        )
    return notification
