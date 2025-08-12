import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from orders.models import ShippingAddress, Order, OrderItem, CartItem
from orders.serializers import ShippingAddressSerializer, OrderSerializer, CartItemSerializer, OrderReceiptSerializer
from orders.enums import OrderStatus, DeliveryType
from users.enums import UserRole
from rest_framework.exceptions import NotFound

logger = logging.getLogger(__name__)


# -------- Permissions --------
class IsVendorOrAdminOrCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        role = getattr(request.user, "role", None)
        if role == UserRole.ADMIN.value:
            return True
        if role == UserRole.VENDOR.value:
            return obj.vendor == request.user
        return obj.customer == request.user


# -------- Order Creation Helpers --------
def create_order_from_cart(user, shipping_data, delivery_type=DeliveryType.STANDARD.value, promo_code=None):
    cart_qs = CartItem.objects.filter(user=user, saved_for_later=False).select_related('product', 'product__vendor')
    if not cart_qs.exists():
        raise ValueError("Cart is empty")

    vendors = {ci.product.vendor for ci in cart_qs}
    if len(vendors) > 1:
        raise ValueError("Cart contains items from multiple vendors. Please checkout per vendor.")

    vendor = vendors.pop()

    with transaction.atomic():
        order = Order.objects.create(
            customer=user,
            vendor=vendor,
            delivery_type=delivery_type,
            promo_code=promo_code,
            subtotal=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            order_status=OrderStatus.PENDING.value,
            payment_status=OrderStatus.PENDING.value,
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

    logger.info(f"Order {order.order_id} created from cart for user {user.id}")
    return order


def create_order_for_single_product(product, user, shipping_data, quantity=1, delivery_type=DeliveryType.STANDARD.value):
    with transaction.atomic():
        order = Order.objects.create(
            customer=user,
            vendor=product.vendor,
            delivery_type=delivery_type,
            order_status=OrderStatus.PENDING.value,
            payment_status=OrderStatus.PENDING.value,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=getattr(product, "price1", product.price)  # safer price handling
        )
        ShippingAddress.objects.create(user=user, order=order, **shipping_data)
        order.update_totals()

    logger.info(f"Order {order.order_id} created for single product {product.id} by user {user.id}")
    return order


# -------- Order ViewSet --------
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdminOrCustomer]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()

        user = self.request.user
        role = getattr(user, "role", None)

        if role == UserRole.ADMIN.value:
            return Order.objects.all()
        elif role == UserRole.VENDOR.value:
            return Order.objects.filter(vendor=user)
        return Order.objects.filter(customer=user)

    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != UserRole.VENDOR.value:
            raise PermissionDenied("Only vendors can manually create orders.")
        instance = serializer.save(vendor=self.request.user, order_status=OrderStatus.PENDING.value)
        logger.info(f"Order {instance.order_id} manually created by vendor {self.request.user.id}")

    def perform_update(self, serializer):
        instance = serializer.save()
        logger.info(f"Order {instance.order_id} updated with status {instance.order_status}")

    @action(detail=False, methods=['post'], url_path='create-from-cart')
    def create_from_cart_action(self, request):
        try:
            shipping_data = request.data.get("shipping_data", {})
            delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)
            promo_code = request.data.get("promo_code")

            if delivery_type not in [d.value for d in DeliveryType]:
                return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)

            shipping_serializer = ShippingAddressSerializer(data=shipping_data)
            shipping_serializer.is_valid(raise_exception=True)

            order = create_order_from_cart(
                user=request.user,
                shipping_data=shipping_serializer.validated_data,
                delivery_type=delivery_type,
                promo_code=promo_code
            )
            return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_201_CREATED)

        except (ValidationError, ValueError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='create-single')
    def create_single_action(self, request):
        from products.models import Product

        try:
            product_id = request.data.get("product_id")
            if not product_id:
                return Response({"error": "Product ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            quantity = int(request.data.get("quantity", 1))
            if quantity < 1:
                return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)

            shipping_data = request.data.get("shipping_data", {})
            delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)

            if delivery_type not in [d.value for d in DeliveryType]:
                return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)

            shipping_serializer = ShippingAddressSerializer(data=shipping_data)
            shipping_serializer.is_valid(raise_exception=True)

            product = Product.objects.get(id=product_id)

            order = create_order_for_single_product(
                product=product,
                user=request.user,
                shipping_data=shipping_serializer.validated_data,
                quantity=quantity,
                delivery_type=delivery_type
            )
            return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_201_CREATED)

        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except (ValidationError, ValueError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='payment-success', permission_classes=[permissions.IsAuthenticated])
    def payment_success(self, request, pk=None):
        order = get_object_or_404(Order, pk=pk, customer=request.user)
        order.payment_status = OrderStatus.PAID.value
        order.order_status = OrderStatus.PROCESSING.value
        order.delivery_date = timezone.now()
        order.save(update_fields=["payment_status", "order_status", "delivery_date"])
        return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_200_OK)


# -------- Shipping Address Create View --------
class AddShippingAddressView(generics.CreateAPIView):
    serializer_class = ShippingAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        order_id = self.request.data.get("order_id")
        order = get_object_or_404(Order, id=order_id, customer=self.request.user)
        serializer.save(user=self.request.user, order=order)
        logger.info(f"Shipping address added to order {order.id} by user {self.request.user.id}")


# -------- Cart ViewSet --------
class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user).select_related('product')

    def create(self, request, *args, **kwargs):
        user = request.user
        data = request.data.copy()
        product_id = data.get("product_id")
        quantity = data.get("quantity", 1)

        if not product_id:
            return Response({"error": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_item = CartItem.objects.get(user=user, product_id=product_id, saved_for_later=False)
            cart_item.quantity = quantity
            cart_item.save(update_fields=["quantity"])
            return Response(self.get_serializer(cart_item).data, status=status.HTTP_200_OK)
        except CartItem.DoesNotExist:
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save(user=user)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        if 'quantity' in serializer.validated_data and serializer.validated_data['quantity'] < 1:
            raise ValidationError({"quantity": "Quantity must be at least 1."})
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        cart_item = self.get_object()
        logger.info(f"Deleting cart item {cart_item.id} for user {request.user.id}")
        return super().destroy(request, *args, **kwargs)
        if product.status != ProductStatus.APPROVED.value:
            raise PermissionDenied("Cannot review unapproved products.")







class OrderReceiptView(generics.RetrieveAPIView):
    serializer_class = OrderReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if getattr(user, "role", None) == UserRole.ADMIN.value:
            return Order.objects.all()

        if getattr(user, "role", None) == UserRole.VENDOR.value:
            return Order.objects.filter(vendor=user)

        if getattr(user, "role", None) == UserRole.CUSTOMER.value:
            return Order.objects.filter(customer=user)

        return Order.objects.none()

    def get_object(self):
        order_id = self.kwargs.get("order_id")
        try:
            return self.get_queryset().get(order_id=order_id)
        except Order.DoesNotExist:
            raise NotFound("Receipt not found for this order.")