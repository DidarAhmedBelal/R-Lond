# orders/serializers.py
from rest_framework import serializers
from decimal import Decimal
from products.models import Product
from products.serializers import ProductSerializer
from .models import Order, OrderItem, ShippingAddress, CartItem
from orders.enums import DeliveryType
from products.enums import ProductStatus

# -------- Shipping Address Serializers --------
class ShippingAddressInlineSerializer(serializers.ModelSerializer):
    """For nesting inside other serializers (no order_id)."""
    class Meta:
        model = ShippingAddress
        fields = [
            "full_name",
            "phone_number",
            "email",
            "street_address",
            "landmark",
            "apartment_name",
            "floor_number",
            "flat_number",
            "city",
            "zip_code",
            "billing_same_as_shipping",
        ]
        extra_kwargs = {
            "full_name": {"required": False, "allow_blank": True},
            "phone_number": {"required": False, "allow_blank": True},
            "street_address": {"required": False, "allow_blank": True},
            "city": {"required": False, "allow_blank": True},
            "zip_code": {"required": False, "allow_blank": True},
            "landmark": {"required": False, "allow_blank": True},
            "apartment_name": {"required": False, "allow_blank": True},
            "floor_number": {"required": False, "allow_blank": True},
            "flat_number": {"required": False, "allow_blank": True},
        }

class ShippingAddressAttachSerializer(ShippingAddressInlineSerializer):
    """For /orders/add-shipping-address/ endpoint (needs order_id)."""
    order_id = serializers.IntegerField(write_only=True, required=True)

    class Meta(ShippingAddressInlineSerializer.Meta):
        fields = ["order_id"] + ShippingAddressInlineSerializer.Meta.fields


# -------- Order Items --------
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "price"]


# -------- Order (Read Serializer) --------
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_addresses = ShippingAddressInlineSerializer(many=True, read_only=True)

    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    vendor_name   = serializers.CharField(source="vendor.get_full_name", read_only=True)

    order_status_display   = serializers.CharField(source="get_order_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    delivery_type_display  = serializers.CharField(source="get_delivery_type_display",  read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_id",
            "customer", "customer_name",
            "vendor", "vendor_name",

            # Monetary
            "subtotal", "discount_amount", "promo_code",
            "tax_amount", "delivery_fee", "total_amount",

            # Delivery
            "delivery_type", "delivery_type_display",
            "delivery_instructions", "estimated_delivery", "delivery_date",

            # Status
            "payment_method", "payment_status", "payment_status_display",
            "order_status", "order_status_display",

            # Other
            "order_date", "item_count", "notes",

            # Related
            "items", "shipping_addresses",
        ]
        read_only_fields = [
            "order_id", "order_date", "items",
            "subtotal", "tax_amount", "delivery_fee", "total_amount",
            "item_count", "order_status", "payment_status",
        ]


# -------- Cart --------
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(status=ProductStatus.APPROVED.value, is_active=True),
        write_only=True,
        source="product"
    )

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "price_snapshot"]
        read_only_fields = ["id", "price_snapshot"]

    def create(self, validated_data):
        user = self.context["request"].user
        product = validated_data["product"]
        quantity = validated_data.get("quantity", 1)
        price_snapshot = product.price1
        cart_item, created = CartItem.objects.update_or_create(
            user=user, product=product,
            defaults={"quantity": quantity, "price_snapshot": price_snapshot}
        )
        return cart_item

    def update(self, instance, validated_data):
        instance.quantity = validated_data.get("quantity", instance.quantity)
        instance.save(update_fields=["quantity"])
        return instance


# -------- Receipt --------
class ReceiptOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name")
    price = serializers.DecimalField(source="product.price1", max_digits=10, decimal_places=2)

    class Meta:
        model = OrderItem
        fields = ["product_name", "quantity", "price"]


class OrderReceiptSerializer(serializers.ModelSerializer):
    items = ReceiptOrderItemSerializer(many=True, read_only=True)
    shipping_address = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    vendor_name   = serializers.CharField(source="vendor.get_full_name",   read_only=True)
    order_status_display   = serializers.CharField(source="get_order_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    delivery_type_display  = serializers.CharField(source="get_delivery_type_display",  read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_id", "order_date", "estimated_delivery",
            "customer_name", "vendor_name",
            "items", "subtotal", "discount_amount", "tax_amount", "delivery_fee", "total_amount",
            "delivery_type_display", "order_status_display", "payment_status_display",
            "payment_method", "shipping_address",
        ]

    def get_shipping_address(self, obj):
        shipping = obj.shipping_addresses.first()
        if shipping:
            return {
                "full_name": shipping.full_name,
                "phone_number": shipping.phone_number,
                "street_address": shipping.street_address,
                "city": shipping.city,
                "zip_code": shipping.zip_code,
            }
        # Fallback to User profile
        user = obj.customer
        return {
            "full_name": user.get_full_name() or "",
            "phone_number": getattr(user, "phone_number", "") or "",
            "street_address": getattr(user, "address", "") or "",
            "city": getattr(user, "city", "") or "",
            "zip_code": getattr(user, "zip_code", "") or "",
        }
