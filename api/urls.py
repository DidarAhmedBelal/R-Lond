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
from orders.views import OrderViewSet, AddShippingAddressView, CartViewSet, OrderReceiptView

from common.views import OrderManagementViewSet

from products.views import TopSellProductViewSet, PromotionViewSet, VendorProductList

from dashboard.views import VendorDashboardView, VendorSalesOverviewView



# Router config
router = DefaultRouter()

# Common
router.register('categories', CategoryViewSet, basename='category')
router.register('tags', TagViewSet, basename='tag')
router.register('seo', SEOViewSet, basename='seo')
router.register('saved-products', SavedProductViewSet, basename='saved-product')
router.register('product-reviews', ReviewViewSet, basename='product-review')

# Products
router.register('products', ProductViewSet, basename='product')
router.register('product-images', ProductImageViewSet, basename='product-image')

# Users
router.register('seller/applications', SellerApplicationViewSet, basename='seller-application')

# Payments
router.register('payments', PaymentViewSet, basename='payment')

# Orders
router.register('orders', OrderViewSet, basename='order')

router.register('cart', CartViewSet, basename='cart')

router.register('vendor/order/list', OrderManagementViewSet, basename='order-manage')

router.register('top-sell-products', TopSellProductViewSet, basename='top-sell-product')

router.register('vendor/products', VendorProductList, basename='vendor-products')

router.register('promotions', PromotionViewSet, basename='promotion')


urlpatterns = [
    # Auth & Profile
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('signup/customer/', CustomerSignupView.as_view(), name='signup-customer'),
    path('seller/apply/', SellerApplicationView.as_view(), name='seller-application-create'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile-update'),
    path('forgot-password/request/', ForgotPasswordRequestView.as_view(), name='forgot-password-request'),
    path('forgot-password/confirm/', ForgotPasswordConfirmView.as_view(), name='forgot-password-confirm'),
    path('orders/add-shipping-address/', AddShippingAddressView.as_view(), name='add-shipping-address'),
    path("receipt/<str:order_id>/", OrderReceiptView.as_view(), name="order-receipt"),

    path('vendor/dashboard/', VendorDashboardView.as_view(), name='vendor-dashboard'),

# GET /api/dashboard/vendor/sales-overview?period=7days
# GET /api/dashboard/vendor/sales-overview?period=30days
# GET /api/dashboard/vendor/sales-overview?period=year

    path("vendor/sales-overview/", VendorSalesOverviewView.as_view(), name="vendor-sales-overview"),


    # Stripe webhook (no trailing slash)
    path('stripe/webhook', StripeWebhookView.as_view(), name='stripe-webhook'),

    # Router URLs
    path('', include(router.urls)),
]
