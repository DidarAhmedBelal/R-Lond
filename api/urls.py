from django.urls import path
from users.views import (
    UserProfileUpdateView,
    ForgotPasswordRequestView,
    ForgotPasswordConfirmView,
    UserLoginView,
    UserListView, 
    CustomerSignupView,
    VendorSignupView
)

urlpatterns = [
    path('users/', UserListView.as_view(), name='user-list'),
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('signup/customer/', CustomerSignupView.as_view(), name='signup-customer'),
    path('signup/vendor/', VendorSignupView.as_view(), name='signup-vendor'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile-update'),
    path('forgot-password/request/', ForgotPasswordRequestView.as_view(), name='forgot-password-request'),
    path('forgot-password/confirm/', ForgotPasswordConfirmView.as_view(), name='forgot-password-confirm'),
]
