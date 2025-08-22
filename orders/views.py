# orders/views.py
import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound

from orders.models import Order, CartItem
from orders.serializers import (
    ShippingAddressAttachSerializer,
    ShippingAddressInlineSerializer,
    OrderSerializer,
    CartItemSerializer,
    OrderReceiptSerializer,
    ShippingAddressSerializer
)
from orders.enums import OrderStatus, DeliveryType
from orders.utils import create_order_from_cart, create_order_for_single_product
from products.models import Product
from users.enums import UserRole
from orders.models import ShippingAddress


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


# -------- Order ViewSet --------
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdminOrCustomer]

    def get_queryset(self):
        user = self.request.user

        if getattr(user, 'role', None) == UserRole.ADMIN.value or getattr(user, 'is_staff', False):
            queryset = Order.objects.all()
        elif getattr(user, 'role', None) == UserRole.VENDOR.value:
            queryset = Order.objects.filter(items__product__vendor=user).distinct()
        elif getattr(user, 'role', None) == UserRole.CUSTOMER.value:
            queryset = Order.objects.filter(customer=user)
        else:
            return Order.objects.none()

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(order_date__date__range=[start_date, end_date])

        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            if payment_status.lower() == 'none':
                queryset = queryset.filter(payment_status__isnull=True)
            elif payment_status.lower() != 'all':
                queryset = queryset.filter(payment_status__iexact=payment_status)

        return queryset.order_by('-order_date')


    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != UserRole.VENDOR.value:
            raise PermissionDenied("Only vendors can manually create orders.")
        instance = serializer.save(vendor=self.request.user, order_status=OrderStatus.PENDING.value)
        logger.info(f"Order {instance.order_id} created by vendor {self.request.user.id}")

    def perform_update(self, serializer):
        instance = serializer.save()
        logger.info(f"Order {instance.order_id} updated with status {instance.order_status}")

    # ---------- Cart Order Creation (NO shipping here) ----------
    @action(detail=False, methods=["post"], url_path="create-from-cart")
    def create_from_cart_action(self, request):
        delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)
        if delivery_type not in [d.value for d in DeliveryType]:
            return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = create_order_from_cart(
                user=request.user,
                delivery_type=delivery_type,
                promo_code=request.data.get("promo_code"),
                discount=request.data.get("discount"),
                delivery_instruction=request.data.get("delivery_instruction"),
                estimated_delivery=request.data.get("estimated_delivery"),
                delivery_date=request.data.get("delivery_date"),
                payment_method=request.data.get("payment_method"),
                notes=request.data.get("notes"),
            )
            return Response(OrderSerializer(order, context={"request": request}).data,
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ---------- Single Product (optional shipping provided) ----------
    @action(detail=False, methods=["post"], url_path="create-single")
    def create_single_action(self, request):
        product_id = request.data.get("product_id")
        if not product_id:
            return Response({"error": "Product ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(request.data.get("quantity", 1))
            if quantity < 1:
                return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)
        if delivery_type not in [d.value for d in DeliveryType]:
            return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            order = create_order_for_single_product(
                product=product,
                user=request.user,
                quantity=quantity,
                delivery_type=delivery_type,
                promo_code=request.data.get("promo_code"),
                discount=request.data.get("discount"),
                delivery_instruction=request.data.get("delivery_instruction"),
                estimated_delivery=request.data.get("estimated_delivery"),
                delivery_date=request.data.get("delivery_date"),
                payment_method=request.data.get("payment_method"),
                notes=request.data.get("notes"),
            )

            # OPTIONAL: if client sent shipping_data, attach now
            shipping_data = request.data.get("shipping_data")
            if shipping_data:
                s = ShippingAddressInlineSerializer(data=shipping_data)
                s.is_valid(raise_exception=True)
                ShippingAddress = order.shipping_addresses.model
                ShippingAddress.objects.create(order=order, **s.validated_data)

            return Response(OrderSerializer(order, context={"request": request}).data,
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ---------- Payment Success (manual) ----------
    @action(detail=True, methods=["post"], url_path="payment-success")
    def payment_success(self, request, pk=None):
        order = get_object_or_404(Order, pk=pk, customer=request.user)
        order.payment_status = OrderStatus.PAID.value
        order.order_status = OrderStatus.PROCESSING.value
        order.delivery_date = timezone.now()
        order.save(update_fields=["payment_status", "order_status", "delivery_date"])
        return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_200_OK)





# -------- Shipping Address Attach --------
class ShippingAddressViewSet(viewsets.ModelViewSet):

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShippingAddressSerializer  # default serializer for listing

    def get_queryset(self):
        # Only show shipping addresses that belong to the logged-in user
        return ShippingAddress.objects.filter(user=self.request.user).select_related("order")

    def get_serializer_class(self):
        # Use attach serializer for create action
        if self.action == 'create':
            return ShippingAddressAttachSerializer
        return ShippingAddressSerializer

    def perform_create(self, serializer):
        # Extract order_id from validated data
        order_id = serializer.validated_data.pop("order_id")
        order = get_object_or_404(Order, id=order_id)

        # Ensure the order belongs to the user
        if order.customer != self.request.user:
            raise PermissionDenied("You do not have permission to add a shipping address to this order.")

        # Create the shipping address linked to the order and user
        ShippingAddress.objects.create(user=self.request.user, order=order, **serializer.validated_data)

        logger.info(f"Shipping address added to order {order.id} by user {self.request.user.id}")

    # Optional: override create to return the serialized object after creation
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Return the full serialized address
        instance = ShippingAddress.objects.filter(user=request.user).latest('id')
        read_serializer = ShippingAddressSerializer(instance)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)




# -------- Cart ViewSet --------
class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user).select_related("product")

    def create(self, request, *args, **kwargs):
        from products.models import Product
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)

        if not product_id:
            return Response({"error": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        cart_item, created = CartItem.objects.update_or_create(
            user=request.user,
            product_id=product_id,
            defaults={"quantity": quantity, "price_snapshot": Product.objects.get(pk=product_id).price1},
        )
        return Response(self.get_serializer(cart_item).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def increment(self, request, pk=None):
        cart_item = self.get_object()
        if getattr(cart_item.product, "stock_quantity", None) and cart_item.quantity + 1 > cart_item.product.stock_quantity:
            return Response({"error": "Cannot exceed available stock."}, status=status.HTTP_400_BAD_REQUEST)
        cart_item.quantity += 1
        cart_item.save(update_fields=["quantity"])
        return Response(self.get_serializer(cart_item).data)

    @action(detail=True, methods=["post"])
    def decrement(self, request, pk=None):
        cart_item = self.get_object()
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save(update_fields=["quantity"])
        return Response(self.get_serializer(cart_item).data)


# -------- Order Receipt --------
class OrderReceiptView(generics.RetrieveAPIView):
    serializer_class = OrderReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        if role == UserRole.ADMIN.value:
            return Order.objects.all()
        if role == UserRole.VENDOR.value:
            return Order.objects.filter(vendor=user)
        if role == UserRole.CUSTOMER.value:
            return Order.objects.filter(customer=user)
        return Order.objects.none()

    def get_object(self):
        order_id = self.kwargs.get("order_id")
        try:
            return self.get_queryset().get(order_id=order_id)
        except Order.DoesNotExist:
            raise NotFound("Receipt not found for this order.")
