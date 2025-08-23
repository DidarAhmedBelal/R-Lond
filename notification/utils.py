from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from user.models import User
from notification.models import Notification
from notification.serializers import NotificationSerializer


def prepare_notification_meta_data(message, sender=None, base_meta_data=None):
    if base_meta_data and base_meta_data.get('type') == 'chat':
        return base_meta_data

    meta_data = base_meta_data or {}
    message_upper = message.upper()

    if sender:
        meta_data['sender_id'] = str(sender.id)
        meta_data['sender_username'] = sender.username

    if "MESSAGE" in message_upper or "CHAT" in message_upper:
        meta_data['type'] = 'chat'
        if base_meta_data:
            meta_data.update({
                'chatroom_id': base_meta_data.get('chatroom_id'),
                'chat_type': base_meta_data.get('chat_type', 'direct'),
                'receiver_id': base_meta_data.get('receiver_id'),
                'group_id': base_meta_data.get('group_id'),
            })
    elif "BID" in message_upper:
        meta_data['type'] = 'bid'
        if base_meta_data:
            meta_data.update({
                'bid_id': base_meta_data.get('bid_id'),
                'project_id': base_meta_data.get('project_id'),
                'bid_amount': base_meta_data.get('bid_amount'),
                'bid_status': base_meta_data.get('bid_status'),
            })
    elif "OFFER" in message_upper:
        meta_data['type'] = 'offer'
        if base_meta_data:
            meta_data.update({
                'offer_id': base_meta_data.get('offer_id'),
                'bid_id': base_meta_data.get('bid_id'),  # Added bid_id
                'project_id': base_meta_data.get('project_id'),
                'offer_amount': base_meta_data.get('offer_amount'),
                'offer_status': base_meta_data.get('offer_status'),
            })
    elif "EXTENSION" in message_upper:
        meta_data['type'] = 'extension'
        if base_meta_data:
            meta_data.update({
                'extension_id': base_meta_data.get('extension_id'),
                'offer_id': base_meta_data.get('offer_id'),
                'bid_id': base_meta_data.get('bid_id'),
                'project_id': base_meta_data.get('project_id'),
                'extension_status': base_meta_data.get('extension_status'),
                'requested_days': base_meta_data.get('requested_days'),
                'new_date': base_meta_data.get('new_date'),
            })
    elif "DELIVERY" in message_upper:
        meta_data['type'] = 'delivery'
        if base_meta_data:
            meta_data.update({
                'delivery_id': base_meta_data.get('delivery_id'),
                'offer_id': base_meta_data.get('offer_id'),
                'bid_id': base_meta_data.get('bid_id'),
                'project_id': base_meta_data.get('project_id'),
                'delivery_status': base_meta_data.get('delivery_status')
            })
    elif "ORDER" in message_upper:
        meta_data['type'] = 'order'
        if base_meta_data:
            meta_data.update({
                'order_id': base_meta_data.get('order_id'),
                'project_id': base_meta_data.get('project_id'),
                'order_status': base_meta_data.get('order_status'),
                'order_amount': base_meta_data.get('order_amount'),
            })
    elif "PROJECT" in message_upper:
        meta_data['type'] = 'project'
        if base_meta_data:
            meta_data.update({
                'project_id': base_meta_data.get('project_id'),
                'project_title': base_meta_data.get('project_title'),
                'project_status': base_meta_data.get('project_status'),
                'project_type': base_meta_data.get('project_type'),
            })
    elif "AGENCY" in message_upper:
        meta_data['type'] = 'agency_profile'
        if base_meta_data:
            meta_data.update({
                'agency_id': base_meta_data.get('agency_id'),
                'agency_name': base_meta_data.get('agency_name'),
            })
    elif "COMPANY" in message_upper:
        meta_data['type'] = 'company_profile'
        if base_meta_data:
            meta_data.update({
                'company_id': base_meta_data.get('company_id'),
                'company_name': base_meta_data.get('company_name'),
            })

    return meta_data

def send_notification_to_user(user, message, sender=None, meta_data=None):
    assert isinstance(user, User)
    if sender:
        assert isinstance(sender, User)

    channel_layer = get_channel_layer()
    notification_meta_data = prepare_notification_meta_data(message, sender, meta_data)

    notification = Notification.objects.create(
        user_id=user.id,
        sender=sender,
        # receiver=user,
        message=message,
        meta_data=notification_meta_data
    )

    notification = Notification.objects.select_related(
        'user',
        'user__companyprofile',
        'user__agencyprofile'
    ).get(id=notification.id)
    
    full_name = None
    if user.role == 'COMPANY' and hasattr(user, 'companyprofile'):
        full_name = user.companyprofile.company_name
    elif user.role == 'AGENCY' and hasattr(user, 'agencyprofile'):
        full_name = user.agencyprofile.agency_name
    else:
        full_name = f"{user.first_name} {user.last_name}".strip() or None

    if user and user.is_active:
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',  
            {
                'type': 'send_notification',
                'notification': {
                    "id": notification.id,
                    "message": message,
                    "time": notification.event_time.isoformat(),
                    "seen": False,
                    "username": user.username,
                    "full_name": full_name,
                    "meta_data": notification.meta_data
                },
            }
        )
    return notification
