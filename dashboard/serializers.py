from rest_framework import serializers
from .models import PayoutRequest
from payments.models import Payment
from payments.enums import PaymentStatusEnum
from django.db import models

class PayoutRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRequest
        fields = ["id", "vendor", "amount", "payment_method", "note", "status", "created_at"]
        read_only_fields = ["id", "vendor", "status", "created_at"]

    def validate_amount(self, value):
        user = self.context["request"].user
        total_earnings = Payment.objects.filter(
            vendor=user,
            status=PaymentStatusEnum.COMPLETED.value
        ).aggregate(total=models.Sum("amount"))["total"] or 0

        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        if value > total_earnings:
            raise serializers.ValidationError("Amount exceeds your total earnings.")
        return value

    def create(self, validated_data):
        validated_data["vendor"] = self.context["request"].user
        return super().create(validated_data)
