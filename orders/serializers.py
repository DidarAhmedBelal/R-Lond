# orders/serializers.py
from rest_framework import serializers
from decimal import Decimal
from products.models import Product
from products.serializers import ProductSerializer
from .models import Order, OrderItem, ShippingAddress, CartItem
from orders.enums import OrderStatus, DeliveryType, PaymentMethod


class ShippingAddressSerializer(serializers.ModelSerializer):
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


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    # Accept shipping address for creation
    shipping_address = ShippingAddressSerializer(write_only=True)
    shipping_addresses = ShippingAddressSerializer(many=True, read_only=True)

    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.get_full_name', read_only=True)

    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    delivery_type_display = serializers.CharField(source='get_delivery_type_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_id',
            'customer', 'customer_name',
            'vendor', 'vendor_name',

            # Monetary
            'subtotal',
            'discount_amount',
            'promo_code',
            'tax_amount',
            'delivery_fee',
            'total_amount',

            # Delivery
            'delivery_type', 'delivery_type_display',
            'delivery_instructions',
            'estimated_delivery',
            'delivery_date',

            # Status
            'payment_method',
            'payment_status', 'payment_status_display',
            'order_status', 'order_status_display',

            # Other
            'order_date',
            'item_count',
            'notes',

            # Related
            'items',
            'shipping_address',       # for create
            'shipping_addresses',     # for read
        ]
        read_only_fields = [
            'order_id',
            'order_date',
            'items',
            'subtotal',
            'tax_amount',
            'delivery_fee',
            'total_amount',
            'item_count',
            'order_status',
            'payment_status',
        ]

    def validate_order_status(self, value):
        valid_statuses = [status.value for status in OrderStatus]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid order status. Valid options: {valid_statuses}")
        return value

    def validate_delivery_type(self, value):
        valid_types = [t.value for t in DeliveryType]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid delivery type. Valid options: {valid_types}")
        return value

    def validate_payment_method(self, value):
        valid_methods = [pm.value for pm in PaymentMethod]
        if value not in valid_methods:
            raise serializers.ValidationError(f"Invalid payment method. Valid options: {valid_methods}")
        return value

    def create(self, validated_data):
        shipping_data = validated_data.pop('shipping_address', None)
        order = super().create(validated_data)

        if shipping_data:
            ShippingAddress.objects.create(order=order, **shipping_data)
        else:
            ShippingAddress.objects.create(
                order=order,
                full_name="N/A",
                phone_number="N/A",
                street_address="N/A",
                city="N/A",
                zip_code="0000"
            )
        return order


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        source='product'
    )

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'price_snapshot']
        read_only_fields = ['id', 'price_snapshot']

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']
        quantity = validated_data.get('quantity', 1)
        price_snapshot = product.price1  # Adjust if needed to your price field

        cart_item, created = CartItem.objects.update_or_create(
            user=user,
            product=product,
            defaults={'quantity': quantity, 'price_snapshot': price_snapshot}
        )
        return cart_item

    def update(self, instance, validated_data):
        quantity = validated_data.get('quantity', instance.quantity)
        instance.quantity = quantity
        instance.save(update_fields=['quantity'])
        return instance


# ---------------------------
# Receipt Serializers
# ---------------------------

class ReceiptOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name")
    price = serializers.DecimalField(source='product.price1', max_digits=10, decimal_places=2)

    class Meta:
        model = OrderItem
        fields = ['product_name', 'quantity', 'price']


class OrderReceiptSerializer(serializers.ModelSerializer):
    items = ReceiptOrderItemSerializer(many=True, read_only=True)
    shipping_address = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.get_full_name', read_only=True)
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    delivery_type_display = serializers.CharField(source='get_delivery_type_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_id',
            'order_date',
            'estimated_delivery',
            'customer_name',
            'vendor_name',
            'items',
            'subtotal',
            'discount_amount',
            'tax_amount',
            'delivery_fee',
            'total_amount',
            'delivery_type_display',
            'order_status_display',
            'payment_status_display',
            'payment_method',
            'shipping_address'
        ]

    def get_shipping_address(self, obj):
        shipping = obj.shipping_addresses.first()
        if not shipping:
            return None
        return {
            "full_name": shipping.full_name,
            "phone_number": shipping.phone_number,
            "street_address": shipping.street_address,
            "city": shipping.city,
            "zip_code": shipping.zip_code
        }
