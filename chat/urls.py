# from django.urls import path

# from chat.views import get_chat_messages, list_user_chats, delete_message, edit_message

# urlpatterns = [
#     path('history/<int:pk>/', get_chat_messages, name='chat'),
#     path('list_user_chats/', list_user_chats, name='chat-list'),
#     path("messages/<int:pk>/delete/", delete_message, name="message-delete"),
# ]


from django.urls import path
from . import views

urlpatterns = [
    path('list_user_chats/', views.UserChatsListView.as_view(), name='list-user-chats'),
    path('history/<int:pk>/', views.ChatMessagesListView.as_view(), name='get-chat-messages'),
    path('message/<int:pk>/delete/', views.MessageDeleteView.as_view(), name='delete-message'),
    path('message/<int:pk>/edit/', views.MessageUpdateView.as_view(), name='edit-message'),
]