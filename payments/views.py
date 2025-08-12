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
from decimal import Decimal
from payments.models import Payment
from payments.serializers import PaymentSerializer
from products.models import Product, ProductStatus
from users.models import User
from rest_framework.exceptions import PermissionDenied
from django.db.models import Sum
from django.utils.timezone import now
from datetime import timedelta
from django.db import models
from orders.enums import OrderStatus
from orders.models import Order
from django.http import JsonResponse, HttpResponse

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
            # Create an Order record BEFORE creating the Stripe session so metadata can include order_id
            order = Order.objects.create(
                customer=user,
                vendor=product.vendor,
                total_amount=product.price1,
                order_status=OrderStatus.PENDING.value,
                payment_status=OrderStatus.PENDING.value,
            )

            # Build success/cancel URLs
            success_url = getattr(settings, 'FRONTEND_PAYMENT_SUCCESS_URL', None) or request.build_absolute_uri('/payments/success/')
            cancel_url = getattr(settings, 'FRONTEND_PAYMENT_CANCEL_URL', None) or request.build_absolute_uri('/payments/cancel/')

            price_to_use = Decimal(product.price1 or 0)
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": product.name},
                        "unit_amount": int(price_to_use * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                customer_email=user.email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "product_id": str(product.id),
                    "customer_id": str(user.id),
                    "vendor_id": str(product.vendor.id),
                    "order_id": str(order.id),
                    "payment": "true",
                },
            )

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
        elif getattr(user, "role", None) == "vendor":
            total_payments_count = Payment.objects.filter(status="completed", vendor=user).count()
            total_payments_amount = Payment.objects.filter(status="completed", vendor=user).aggregate(total=Sum("amount"))["total"] or 0
            data = {
                "total_payments_count": total_payments_count,
                "total_payments_amount": total_payments_amount,
            }
        elif getattr(user, "role", None) == "customer":
            total_payments_count = Payment.objects.filter(status="completed", customer=user).count()
            total_payments_amount = Payment.objects.filter(status="completed", customer=user).aggregate(total=Sum("amount"))["total"] or 0
            data = {
                "total_payments_count": total_payments_count,
                "total_payments_amount": total_payments_amount,
            }
        else:
            data = {"detail": "No payment data available for your role."}

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def payments_graph(self, request):
        user = request.user
        today = now()
        start_date = (today.replace(day=1) - timedelta(days=365)).replace(day=1)

        months = []
        month_data = {}
        dt = start_date
        for _ in range(12):
            key = dt.strftime("%Y-%m")
            months.append(key)
            month_data[key] = 0
            if dt.month == 12:
                dt = dt.replace(year=dt.year + 1, month=1)
            else:
                dt = dt.replace(month=dt.month + 1)

        payments_qs = Payment.objects.filter(status="completed", created_at__gte=start_date)

        if user.is_staff or user.is_superuser:
            pass
        elif getattr(user, "role", None) == "vendor":
            payments_qs = payments_qs.filter(vendor=user)
        elif getattr(user, "role", None) == "customer":
            payments_qs = payments_qs.filter(customer=user)
        else:
            return Response({"detail": "No payment data available for your role."}, status=status.HTTP_403_FORBIDDEN)

        payments_by_month = payments_qs.annotate(
            year=models.functions.ExtractYear("created_at"),
            month=models.functions.ExtractMonth("created_at")
        ).values("year", "month").annotate(total_amount=Sum("amount")).order_by("year", "month")

        for entry in payments_by_month:
            key = f"{entry['year']}-{entry['month']:02d}"
            if key in month_data:
                month_data[key] = float(entry["total_amount"]) if entry["total_amount"] else 0

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
            logger.error(f"Error parsing Stripe webhook: {e}", exc_info=True)
            return Response({"error": "Webhook error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            metadata = session.get("metadata", {}) or {}
            transaction_id = session.get("id")

            # Prevent duplicate payment
            if Payment.objects.filter(transaction_id=transaction_id).exists():
                logger.warning(f"Duplicate payment attempt ignored: {transaction_id}")
                return Response({"status": "duplicate_ignored"}, status=status.HTTP_200_OK)

            try:
                product = None
                customer = None
                vendor = None
                order = None

                if metadata.get("product_id"):
                    product = Product.objects.filter(id=metadata.get("product_id")).first()
                if metadata.get("customer_id"):
                    customer = User.objects.filter(id=metadata.get("customer_id")).first()
                if metadata.get("vendor_id"):
                    vendor = User.objects.filter(id=metadata.get("vendor_id")).first()

                order_id = metadata.get("order_id")
                if order_id:
                    order = Order.objects.filter(id=order_id).first()

                if not order:
                    order = Order.objects.create(
                        customer=customer,
                        vendor=vendor,
                        total_amount=(Decimal(session.get("amount_total") or 0) / 100) if session.get("amount_total") else None,
                        order_status=OrderStatus.PAID.value,
                        payment_status=OrderStatus.PAID.value,
                    )

                amount = Decimal(session.get("amount_total") or 0) / 100
                Payment.objects.create(
                    product=product,
                    customer=customer,
                    vendor=vendor,
                    amount=amount,
                    payment_method="stripe",
                    transaction_id=transaction_id,
                    status="completed",
                )

                # Update order status to 'paid'
                order.order_status = OrderStatus.PAID.value
                order.payment_status = OrderStatus.PAID.value
                order.save()

                logger.info(f"Payment successful & Order {order.id} marked as PAID")
                return Response({"status": "payment_success"}, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error recording payment: {e}", exc_info=True)
                # Return 200 so Stripe doesn't retry repeatedly
                return Response({"error": "Payment processing error"}, status=status.HTTP_200_OK)

        logger.info(f"Unhandled event type: {event['type']}")
        return Response({"status": "event_not_handled"}, status=status.HTTP_200_OK)


class PaymentSuccessView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        frontend_success = getattr(settings, 'FRONTEND_PAYMENT_SUCCESS_URL', None)
        if frontend_success:
            return JsonResponse({"detail": "Payment successful. Please check your order."})
        return HttpResponse("Payment successful. You can close this window.")


class PaymentCancelView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        frontend_cancel = getattr(settings, 'FRONTEND_PAYMENT_CANCEL_URL', None)
        if frontend_cancel:
            return JsonResponse({"detail": "Payment canceled."})
        return HttpResponse("Payment canceled. You can close this window.")
