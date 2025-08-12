import logging
from decimal import Decimal
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from orders.models import Order, OrderItem, ShippingAddress
from orders.serializers import OrderSerializer
from orders.enums import OrderStatus, DeliveryType
from users.enums import UserRole
from orders.models import CartItem

logger = logging.getLogger(__name__)


# -------- Permissions --------
class IsVendorOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) in [UserRole.ADMIN.value, UserRole.VENDOR.value]


# -------- Order Creation Helpers --------
def create_order_from_cart(user, shipping_data, delivery_type=DeliveryType.STANDARD.value, promo_code=None):
    cart_qs = CartItem.objects.filter(user=user, saved_for_later=False)
    if not cart_qs.exists():
        raise ValueError("Cart is empty")

    vendors = set(ci.product.vendor for ci in cart_qs)
    if len(vendors) > 1:
        raise ValueError("Cart contains items from multiple vendors. Checkout per vendor is required.")

    vendor = vendors.pop()

    with transaction.atomic():
        order = Order.objects.create(
            customer=user,
            vendor=vendor,
            delivery_type=delivery_type,
            delivery_instructions="",
            promo_code=promo_code,
            subtotal=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            order_status=OrderStatus.PENDING.value,
        )

        for ci in cart_qs:
            OrderItem.objects.create(
                order=order,
                product=ci.product,
                quantity=ci.quantity,
                price=ci.price_snapshot,
            )

        ShippingAddress.objects.create(user=user, order=order, **shipping_data)
        order.update_totals()

        cart_qs.delete()

    return order


def create_order_for_single_product(product, user, shipping_data, quantity=1, delivery_type=DeliveryType.STANDARD.value):
    with transaction.atomic():
        order = Order.objects.create(
            customer=user,
            vendor=product.vendor,
            delivery_type=delivery_type,
            order_status=OrderStatus.PENDING.value
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price1
        )
        ShippingAddress.objects.create(user=user, order=order, **shipping_data)
        order.update_totals()
    return order


# -------- Order ViewSet --------
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()

        user = self.request.user
        if getattr(user, "role", None) == UserRole.ADMIN.value:
            return Order.objects.all()
        if getattr(user, "role", None) == UserRole.VENDOR.value:
            return Order.objects.filter(vendor=user)
        raise PermissionDenied("You do not have permission to view orders.")

    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != UserRole.VENDOR.value:
            raise PermissionDenied("Only vendors can create orders.")
        instance = serializer.save(vendor=self.request.user, order_status=OrderStatus.PENDING.value)
        logger.info(f"Order {instance.id} created by vendor {self.request.user.id}")

    def perform_update(self, serializer):
        instance = serializer.save()
        logger.info(f"Order {instance.id} updated with status {instance.order_status}")

    # ---- Extra actions ----
    @action(detail=False, methods=['post'], url_path='create-from-cart')
    def create_from_cart(self, request):
        try:
            shipping_data = request.data.get("shipping_data", {})
            delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)
            promo_code = request.data.get("promo_code")

            if delivery_type not in [d.value for d in DeliveryType]:
                return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)

            order = create_order_from_cart(
                user=request.user,
                shipping_data=shipping_data,
                delivery_type=delivery_type,
                promo_code=promo_code
            )
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='create-single')
    def create_single(self, request):
        from products.models import Product

        try:
            product_id = request.data.get("product_id")
            quantity = int(request.data.get("quantity", 1))
            shipping_data = request.data.get("shipping_data", {})
            delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)

            if delivery_type not in [d.value for d in DeliveryType]:
                return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)

            product = Product.objects.get(id=product_id)
            order = create_order_for_single_product(
                product=product,
                user=request.user,
                shipping_data=shipping_data,
                quantity=quantity,
                delivery_type=delivery_type
            )
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
