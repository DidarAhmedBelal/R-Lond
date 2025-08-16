from django.db import models
from django.conf import settings
from django.utils.timezone import now
from payments.enums import PaymentMethodEnum
from dashboard.enums import PayoutStatusEnum

class PayoutRequest(models.Model):
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payout_requests",
        limit_choices_to={"role": "vendor"}
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.value) for tag in PaymentMethodEnum]
    )
    note = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=PayoutStatusEnum.choices(),
        default=PayoutStatusEnum.PENDING.value
    )
    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payout #{self.id} - {self.vendor} - {self.amount} ({self.status})"
