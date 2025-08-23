# chat/utils.py

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from chat.models import Chat
from orders.models import Order

def get_or_create_offer_chat(user1, user2, offer_id):
    offer = get_object_or_404(Order, pk=offer_id)

    if offer.status not in ['accepted', 'negotiation']:
        raise PermissionDenied("Chat is not allowed unless offer is accepted or under negotiation.")

    chat, created = Chat.objects.get_or_create(
        sender=user1,
        receiver=user2,
        offer=offer
    )
    return chat
