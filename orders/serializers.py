from rest_framework import serializers
from .models import Order, OrderItem
from products.serializers import ProductSerializer
from orders.enums import OrderStatus, DeliveryType


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
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
            'items',
        ]
        read_only_fields = [
            'order_id', 'order_date', 'items',
            'subtotal', 'tax_amount', 'delivery_fee', 'total_amount', 'item_count'
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
