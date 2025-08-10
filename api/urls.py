from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import (
    SellerApplicationView,
    SellerApplicationViewSet,
    UserLoginView,
    CustomerSignupView,
    UserProfileView,
    UserProfileUpdateView,
    ForgotPasswordRequestView,
    ForgotPasswordConfirmView,
)
from products.views import CategoryViewSet, ProductViewSet, ProductImageViewSet, ReviewViewSet, CartItemViewSet, WishlistViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='categories')
router.register('products', ProductViewSet, basename='products')
router.register('product-images', ProductImageViewSet, basename='image')
router.register('product-reviews', ReviewViewSet, basename='product-reviews')
router.register('cart-items', CartItemViewSet, basename='items')
router.register('wishlist', WishlistViewSet, basename='wishlist')
router.register('seller/applications', SellerApplicationViewSet, basename='seller-application')

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('signup/customer/', CustomerSignupView.as_view(), name='signup-customer'),
    path('seller/apply/', SellerApplicationView.as_view(), name='seller-application-create'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile-update'),
    path('forgot-password/request/', ForgotPasswordRequestView.as_view(), name='forgot-password-request'),
    path('forgot-password/confirm/', ForgotPasswordConfirmView.as_view(), name='forgot-password-confirm'),
    path('', include(router.urls)),
]
