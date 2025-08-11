from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.shortcuts import get_object_or_404
import stripe
import logging
from payments.models import Payment
from payments.serializers import PaymentSerializer
from payments.stripe_utils import create_checkout_session
from products.models import Product, ProductStatus
from users.models import User
from rest_framework.exceptions import PermissionDenied
from django.db.models import Sum, Count
from django.utils.timezone import now
from datetime import datetime, timedelta
from django.db import models

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Payment.objects.select_related("product", "vendor", "customer")
        if getattr(user, "role", None) == "vendor":
            return Payment.objects.select_related("product", "vendor", "customer").filter(vendor=user)
        if getattr(user, "role", None) == "customer":
            return Payment.objects.select_related("product", "vendor", "customer").filter(customer=user)
        return Payment.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "role", None) != "customer":
            raise PermissionDenied("Only customers can make payments.")
        product = serializer.validated_data.get("product")
        if product.status != ProductStatus.APPROVED.value:
            raise PermissionDenied("You can only purchase approved products.")
        serializer.save(customer=user, vendor=product.vendor)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def create_checkout_session(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk)
        user = request.user

        if getattr(user, "role", None) != "customer":
            return Response({"detail": "Only customers can purchase products."}, status=status.HTTP_403_FORBIDDEN)
        if product.status != ProductStatus.APPROVED.value:
            return Response({"detail": "Product is not approved."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            success_url = request.build_absolute_uri("/payments/success/")
            cancel_url = request.build_absolute_uri("/payments/cancel/")
            session = create_checkout_session(product, user, success_url, cancel_url)
            return Response({"checkout_url": session.url}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Stripe checkout session creation failed: {e}", exc_info=True)
            return Response({"detail": "Failed to create checkout session."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def dashboard_summary(self, request):
        user = request.user
        if user.is_staff or user.is_superuser:
            total_payments_count = Payment.objects.filter(status="completed").count()
            total_payments_amount = Payment.objects.filter(status="completed").aggregate(total=Sum("amount"))["total"] or 0

            vendor_payments_count = Payment.objects.filter(status="completed", vendor__role="vendor").count()
            vendor_payments_amount = Payment.objects.filter(status="completed", vendor__role="vendor").aggregate(total=Sum("amount"))["total"] or 0

            customer_payments_count = Payment.objects.filter(status="completed", customer__role="customer").count()
            customer_payments_amount = Payment.objects.filter(status="completed", customer__role="customer").aggregate(total=Sum("amount"))["total"] or 0

            data = {
                "total_payments_count": total_payments_count,
                "total_payments_amount": total_payments_amount,
                "vendor_payments_count": vendor_payments_count,
                "vendor_payments_amount": vendor_payments_amount,
                "customer_payments_count": customer_payments_count,
                "customer_payments_amount": customer_payments_amount,
            }
        # Vendor summary for own payments received
        elif getattr(user, "role", None) == "vendor":
            total_payments_count = Payment.objects.filter(status="completed", vendor=user).count()
            total_payments_amount = Payment.objects.filter(status="completed", vendor=user).aggregate(total=Sum("amount"))["total"] or 0
            data = {
                "total_payments_count": total_payments_count,
                "total_payments_amount": total_payments_amount,
            }
        # Customer summary for own payments made
        elif getattr(user, "role", None) == "customer":
            total_payments_count = Payment.objects.filter(status="completed", customer=user).count()
            total_payments_amount = Payment.objects.filter(status="completed", customer=user).aggregate(total=Sum("amount"))["total"] or 0
            data = {
                "total_payments_count": total_payments_count,
                "total_payments_amount": total_payments_amount,
            }
        else:
            data = {
                "detail": "No payment data available for your role."
            }

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def payments_graph(self, request):
        """
        Return monthly payment amounts for past 12 months for dashboard graph/chart
        """
        user = request.user
        today = now()
        start_date = (today.replace(day=1) - timedelta(days=365)).replace(day=1)

        # Prepare dictionary with last 12 months keys in "YYYY-MM" format
        months = []
        month_data = {}
        dt = start_date
        for _ in range(12):
            key = dt.strftime("%Y-%m")
            months.append(key)
            month_data[key] = 0
            # increment month
            if dt.month == 12:
                dt = dt.replace(year=dt.year + 1, month=1)
            else:
                dt = dt.replace(month=dt.month + 1)

        # Filter payments by user role and date
        payments_qs = Payment.objects.filter(status="completed", created_at__gte=start_date)

        if user.is_staff or user.is_superuser:
            # all payments
            pass
        elif getattr(user, "role", None) == "vendor":
            payments_qs = payments_qs.filter(vendor=user)
        elif getattr(user, "role", None) == "customer":
            payments_qs = payments_qs.filter(customer=user)
        else:
            return Response({"detail": "No payment data available for your role."}, status=status.HTTP_403_FORBIDDEN)

        # Annotate payments by year and month and sum amounts
        payments_by_month = payments_qs.annotate(
            year=models.functions.ExtractYear("created_at"),
            month=models.functions.ExtractMonth("created_at")
        ).values("year", "month").annotate(total_amount=Sum("amount")).order_by("year", "month")

        for entry in payments_by_month:
            key = f"{entry['year']}-{entry['month']:02d}"
            if key in month_data:
                month_data[key] = float(entry["total_amount"])

        data = {
            "months": months,
            "payments": [month_data[m] for m in months]
        }

        return Response(data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe webhook signature verification failed: {e}")
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error parsing Stripe webhook: {e}")
            return Response({"error": "Webhook error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Handle checkout.session.completed event
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            metadata = session.get("metadata", {})
            transaction_id = session.get("id")

            # Check duplicate payment
            if Payment.objects.filter(transaction_id=transaction_id).exists():
                return Response({"status": "duplicate_ignored"}, status=status.HTTP_200_OK)

            try:
                product = Product.objects.get(id=metadata.get("product_id"))
                customer = User.objects.get(id=metadata.get("customer_id"))
                vendor = User.objects.get(id=metadata.get("vendor_id"))

                payment = Payment.objects.create(
                    product=product,
                    customer=customer,
                    vendor=vendor,
                    amount=session.get("amount_total") / 100.0,
                    payment_method="stripe",
                    transaction_id=transaction_id,
                    status="completed",
                )
                logger.info(f"Payment recorded: {payment.id}")
                return Response({"status": "payment_success"}, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error recording payment: {e}", exc_info=True)
                return Response({"error": "Payment processing error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(f"Unhandled event type: {event['type']}")
        return Response({"status": "event_not_handled"}, status=status.HTTP_200_OK)
