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
