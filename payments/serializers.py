from rest_framework import serializers
from payments.models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    vendor_name = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "product",
            "product_name",
            "vendor",
            "vendor_name",
            "customer",
            "customer_name",
            "amount",
            "payment_method",
            "transaction_id",
            "status",
            "note",
            "created_at",
            "updated_at"
        ]
        read_only_fields = [
            "id",
            "vendor",
            "status",
            "transaction_id",
            "created_at",
            "updated_at"
        ]

    def get_vendor_name(self, obj):
        if obj.vendor:
            return obj.vendor.get_full_name()
        return None

    def get_customer_name(self, obj):
        if obj.customer:
            return obj.customer.get_full_name()
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        if user and getattr(user, "role", None) == "customer":
            validated_data["customer"] = user

        product = validated_data.get("product")
        if product:
            validated_data["vendor"] = product.vendor

        return super().create(validated_data)
