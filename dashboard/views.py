from django.utils import timezone
from django.db.models import Sum, Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import timedelta
from products.models import Product
from orders.models import Order
from orders.enums import OrderStatus
from django.db.models.functions import TruncDate, TruncMonth
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.db.models import Sum
from payments.models import Payment
from payments.enums import PaymentStatusEnum
from .models import PayoutRequest, PayoutStatusEnum
from .serializers import PayoutRequestSerializer
from users.enums import UserRole
from rest_framework.decorators import action
import calendar


class VendorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get_percentage_change(self, current, previous):
        if previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 1)

    def get(self, request):
        user = request.user
        now = timezone.now()

        # === PRODUCTS ===
        products_qs = Product.objects.filter(vendor=user)
        total_products = products_qs.count()

        # Last month product count
        start_last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        end_last_month = now.replace(day=1) - timedelta(days=1)
        last_month_products = Product.objects.filter(
            vendor=user,
            created_at__gte=start_last_month,
            created_at__lte=end_last_month
        ).count()

        products_change = self.get_percentage_change(total_products, last_month_products)

        # === SALES THIS MONTH ===
        start_month = now.replace(day=1)
        start_last_week = now - timedelta(days=7)
        start_prev_week = start_last_week - timedelta(days=7)
        end_prev_week = start_last_week

        sales_this_month = Order.objects.filter(
            vendor=user,
            created_at__gte=start_month,
            created_at__lte=now,
            order_status=OrderStatus.DELIVERED.value
        ).aggregate(total_sales=Sum('items__quantity'))['total_sales'] or 0

        sales_this_week = Order.objects.filter(
            vendor=user,
            created_at__gte=start_last_week,
            created_at__lte=now,
            order_status=OrderStatus.DELIVERED.value
        ).aggregate(total_sales=Sum('items__quantity'))['total_sales'] or 0

        sales_prev_week = Order.objects.filter(
            vendor=user,
            created_at__gte=start_prev_week,
            created_at__lte=end_prev_week,
            order_status=OrderStatus.DELIVERED.value
        ).aggregate(total_sales=Sum('items__quantity'))['total_sales'] or 0

        sales_week_change = self.get_percentage_change(sales_this_week, sales_prev_week)

        # === PENDING ORDERS ===
        pending_orders = Order.objects.filter(
            vendor=user,
            order_status=OrderStatus.PENDING.value
        ).count()

        pending_last_week = Order.objects.filter(
            vendor=user,
            order_status=OrderStatus.PENDING.value,
            created_at__gte=start_prev_week,
            created_at__lte=end_prev_week
        ).count()

        pending_change = self.get_percentage_change(pending_orders, pending_last_week)

        # === EARNINGS THIS MONTH ===
        earnings_this_month = Order.objects.filter(
            vendor=user,
            created_at__gte=start_month,
            created_at__lte=now,
            order_status=OrderStatus.DELIVERED.value
        ).aggregate(total_earnings=Sum('total_amount'))['total_earnings'] or 0

        earnings_last_month = Order.objects.filter(
            vendor=user,
            created_at__gte=start_last_month,
            created_at__lte=end_last_month,
            order_status=OrderStatus.DELIVERED.value
        ).aggregate(total_earnings=Sum('total_amount'))['total_earnings'] or 0

        earnings_change = self.get_percentage_change(earnings_this_month, earnings_last_month)

        return Response({
            "total_products": {
                "count": total_products,
                "change": products_change
            },
            "sales_this_month": {
                "count": sales_this_month,
                "week_change": sales_week_change
            },
            "pending_orders": {
                "count": pending_orders,
                "change": pending_change
            },
            "earnings_this_month": {
                "amount": earnings_this_month,
                "change": earnings_change
            }
        })









class VendorSalesOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        period = request.query_params.get("period", "7days") 

        data = []

        if period == "7days":
            start_date = now - timedelta(days=6)
            date_range = [start_date + timedelta(days=i) for i in range(7)]

            sales = (
                Order.objects.filter(
                    vendor=user,
                    created_at__date__gte=start_date.date(),
                    created_at__date__lte=now.date(),
                    order_status=OrderStatus.DELIVERED.value
                )
                .annotate(date=TruncDate("created_at"))
                .values("date")
                .annotate(total=Sum("total_amount"))
            )
            sales_dict = {s["date"]: float(s["total"] or 0) for s in sales}

            data = [
                {"date": d.strftime("%a"), "value": sales_dict.get(d.date(), 0.0)}
                for d in date_range
            ]

        elif period == "30days":
            start_date = now - timedelta(days=29)
            date_range = [start_date + timedelta(days=i) for i in range(30)]

            sales = (
                Order.objects.filter(
                    vendor=user,
                    created_at__date__gte=start_date.date(),
                    created_at__date__lte=now.date(),
                    order_status=OrderStatus.DELIVERED.value
                )
                .annotate(date=TruncDate("created_at"))
                .values("date")
                .annotate(total=Sum("total_amount"))
            )
            sales_dict = {s["date"]: float(s["total"] or 0) for s in sales}

            data = [
                {"date": d.strftime("%d %b"), "value": sales_dict.get(d.date(), 0.0)}
                for d in date_range
            ]

        elif period == "year":
            start_date = now.replace(month=1, day=1)
            months = [start_date.replace(month=m) for m in range(1, now.month + 1)]

            sales = (
                Order.objects.filter(
                    vendor=user,
                    created_at__date__gte=start_date.date(),
                    created_at__date__lte=now.date(),
                    order_status=OrderStatus.DELIVERED.value
                )
                .annotate(month=TruncMonth("created_at"))
                .values("month")
                .annotate(total=Sum("total_amount"))
            )
            sales_dict = {s["month"].date(): float(s["total"] or 0) for s in sales}

            data = [
                {"date": m.strftime("%b"), "value": sales_dict.get(m.date(), 0.0)}
                for m in months
            ]

        else:
            return Response({"error": "Invalid period"}, status=400)

        return Response({"sales_overview": data})




class IsVendor(permissions.BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == UserRole.VENDOR.value

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == UserRole.ADMIN.value






class PayoutRequestViewSet(viewsets.ModelViewSet):
    queryset = PayoutRequest.objects.all()
    serializer_class = PayoutRequestSerializer

    def get_permissions(self):
        if self.action in ["create", "my_payouts", "total_earnings"]:
            return [permissions.IsAuthenticated(), IsVendor()]
        if self.action in ["approve", "reject", "list_all"]:
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [permissions.IsAuthenticated()]

    # Vendor: My payouts
    @action(detail=False, methods=["get"])
    def my_payouts(self, request):
        payouts = PayoutRequest.objects.filter(vendor=request.user)
        serializer = self.get_serializer(payouts, many=True)
        return Response(serializer.data)

    # Vendor: Create payout request
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        payout = serializer.save(vendor=request.user, status=PayoutStatusEnum.PENDING.value)
        return Response(self.get_serializer(payout).data, status=status.HTTP_201_CREATED)

    # Admin: List all payouts
    @action(detail=False, methods=["get"])
    def list_all(self, request):
        payouts = PayoutRequest.objects.all()
        serializer = self.get_serializer(payouts, many=True)
        return Response(serializer.data)

    # Admin: Approve payout
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        payout = self.get_object()

        if payout.status == PayoutStatusEnum.APPROVED.value:
            return Response({"detail": "Payout already approved."}, status=status.HTTP_400_BAD_REQUEST)

        payout.status = PayoutStatusEnum.APPROVED.value
        payout.save()

        return Response({"detail": "Payout approved successfully."}, status=status.HTTP_200_OK)

    # Admin: Reject payout
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        payout = self.get_object()

        if payout.status == PayoutStatusEnum.REJECTED.value:
            return Response({"detail": "Payout already rejected."}, status=status.HTTP_400_BAD_REQUEST)

        payout.status = PayoutStatusEnum.REJECTED.value
        payout.save()

        return Response({"detail": "Payout rejected successfully."}, status=status.HTTP_200_OK)

    # Vendor: Total earnings
    @action(detail=False, methods=["get"])
    def total_earnings(self, request):
        total = Payment.objects.filter(
            vendor=request.user,
            status=PaymentStatusEnum.COMPLETED.value
        ).aggregate(total=Sum("amount"))["total"] or 0
        return Response({"total_earnings": total})










class VendorPaymentsStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_percentage_change(self, current, previous):
        if previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 1)

    def get(self, request):
        user = request.user
        now = timezone.now()

        # --- DATES ---
        start_month = now.replace(day=1)
        start_last_month = (start_month - timedelta(days=1)).replace(day=1)
        end_last_month = start_month - timedelta(days=1)

        start_week = now - timedelta(days=7)
        prev_week_start = start_week - timedelta(days=7)
        prev_week_end = start_week

        # --- TOTAL SALES ---
        total_sales = Payment.objects.filter(
            vendor=user,
            status=PaymentStatusEnum.COMPLETED.value
        ).aggregate(total=Sum("amount"))["total"] or 0

        last_month_sales = Payment.objects.filter(
            vendor=user,
            status=PaymentStatusEnum.COMPLETED.value,
            created_at__gte=start_last_month,
            created_at__lte=end_last_month
        ).aggregate(total=Sum("amount"))["total"] or 0

        sales_change = self.get_percentage_change(total_sales, last_month_sales)

        # --- PAID OUT ---
        paid_out = Payment.objects.filter(
            vendor=user,
            status=PaymentStatusEnum.COMPLETED.value
        ).count()

        paid_out_last_week = Payment.objects.filter(
            vendor=user,
            status=PaymentStatusEnum.COMPLETED.value,
            created_at__gte=prev_week_start,
            created_at__lte=prev_week_end
        ).count()

        paid_out_this_week = Payment.objects.filter(
            vendor=user,
            status=PaymentStatusEnum.COMPLETED.value,
            created_at__gte=start_week,
            created_at__lte=now
        ).count()

        paid_out_week_change = self.get_percentage_change(paid_out_this_week, paid_out_last_week)

        # --- PENDING PAYOUT ---
        pending_payout = PayoutRequest.objects.filter(
            vendor=user,
            status=PayoutStatusEnum.PENDING.value
        ).count()

        pending_last_week = PayoutRequest.objects.filter(
            vendor=user,
            status=PayoutStatusEnum.PENDING.value,
            created_at__gte=prev_week_start,
            created_at__lte=prev_week_end
        ).count()

        pending_change = self.get_percentage_change(pending_payout, pending_last_week)

        # --- TOTAL ORDERS ---
        total_orders = Order.objects.filter(
            vendor=user
        ).count()

        last_week_orders = Order.objects.filter(
            vendor=user,
            created_at__gte=prev_week_start,
            created_at__lte=prev_week_end
        ).count()

        this_week_orders = Order.objects.filter(
            vendor=user,
            created_at__gte=start_week,
            created_at__lte=now
        ).count()

        orders_change = self.get_percentage_change(this_week_orders, last_week_orders)

        return Response({
            "total_sales": {
                "amount": total_sales,
                "change": sales_change
            },
            "paid_out": {
                "count": paid_out,
                "week_change": paid_out_week_change
            },
            "pending_payout": {
                "count": pending_payout,
                "change": pending_change
            },
            "total_orders": {
                "count": total_orders,
                "change": orders_change
            }
        })









class VendorSalesPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        start_of_year = now.replace(month=1, day=1)

        # Get total sales per month
        monthly_sales = (
            Payment.objects.filter(
                vendor=user,
                status=PaymentStatusEnum.COMPLETED.value,
                created_at__gte=start_of_year,
                created_at__lte=now
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )

        # Prepare all months Jan–Dec with 0 as default
        sales_data = [
            {"month": calendar.month_name[m], "value": 0} for m in range(1, 13)
        ]

        # Fill in sales values
        for entry in monthly_sales:
            month_num = entry["month"].month
            sales_data[month_num - 1]["value"] = float(entry["total"] or 0)

        return Response({"sales_performance": sales_data})
