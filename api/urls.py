from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Users
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

# Products
from products.views import ProductViewSet, ProductImageViewSet

# Common
from common.views import (
    CategoryViewSet,
    TagViewSet,
    SEOViewSet,
    SavedProductViewSet,
    ReviewViewSet,
)

# Payments
from payments.views import PaymentViewSet, StripeWebhookView

# Orders
from orders.views import OrderViewSet


router = DefaultRouter()

# Register routes for common apps
router.register('categories', CategoryViewSet, basename='categories')
router.register('tags', TagViewSet, basename='tags')
router.register('seo', SEOViewSet, basename='seo')
router.register('saved-products', SavedProductViewSet, basename='saved-products')
router.register('product-reviews', ReviewViewSet, basename='product-reviews')

# Products routes
router.register('products', ProductViewSet, basename='products')
router.register('product-images', ProductImageViewSet, basename='product-images')

# Users routes
router.register('seller/applications', SellerApplicationViewSet, basename='seller-application')

# Payments routes
router.register('payments', PaymentViewSet, basename='payment')

# Orders routes
router.register('orders', OrderViewSet, basename='order')


urlpatterns = [
    # Auth & Profile
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('signup/customer/', CustomerSignupView.as_view(), name='signup-customer'),
    path('seller/apply/', SellerApplicationView.as_view(), name='seller-application-create'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile-update'),
    path('forgot-password/request/', ForgotPasswordRequestView.as_view(), name='forgot-password-request'),
    path('forgot-password/confirm/', ForgotPasswordConfirmView.as_view(), name='forgot-password-confirm'),

    # Stripe webhook endpoint - no trailing slash recommended for Stripe webhooks
    path('stripe/webhook', StripeWebhookView.as_view(), name='stripe-webhook'),

    # Include all registered router URLs
    path('', include(router.urls)),
]
