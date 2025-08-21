from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from products.models import Product, ProductImage, Promotion
from common.models import Category, Tag, SEO
from products.enums import DiscountType
from django.db.models import Q
from products.models import ReturnProduct
from products.models import ReturnProduct
from common.models import ImageUpload
from users.enums import UserRole
from orders.models import OrderItem
from orders.enums import OrderStatus



class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        product = attrs.get("product") or getattr(self.instance, "product", None)
        if attrs.get("is_primary") and product:
            if ProductImage.objects.filter(product=product, is_primary=True)\
                    .exclude(pk=getattr(self.instance, "pk", None)).exists():
                raise serializers.ValidationError({
                    "is_primary": "This product already has a primary image."
                })
        return attrs


class PromotionSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), many=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = [
            "id", "name", "discount_type", "discount_value", "products",
            "start_datetime", "end_datetime", "description",
            "is_active", "status",
        ]

    def get_status(self, obj):
        return obj.status

    def validate(self, attrs):
        if attrs["discount_type"] == DiscountType.PERCENTAGE.value:
            if attrs["discount_value"] < 0 or attrs["discount_value"] > 100:
                raise serializers.ValidationError(
                    {"discount_value": "Percentage discount must be between 0 and 100."}
                )
        if attrs["end_datetime"] <= attrs["start_datetime"]:
            raise serializers.ValidationError(
                {"end_datetime": "End date must be after start date."}
            )
        return attrs


class ProductSerializer(serializers.ModelSerializer):
    prod_id = serializers.CharField(read_only=True)
    vendor = serializers.HiddenField(default=serializers.CurrentUserDefault())
    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=Category.objects.all(), required=False)
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all(), required=False)
    seo = serializers.PrimaryKeyRelatedField(queryset=SEO.objects.all(), required=False, allow_null=True)

    # Read existing images
    images = ProductImageSerializer(many=True, read_only=True)
    # Accept new images on create/update
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )

    active_price = serializers.SerializerMethodField()
    promotion_discount = serializers.SerializerMethodField()
    promotion_details = serializers.SerializerMethodField()
    average_rating = serializers.FloatField(read_only=True)
    available_stock = serializers.IntegerField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    total_quantity_sold = serializers.SerializerMethodField()
    total_discount = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'prod_id', 'vendor', 'categories', 'tags', 'seo',
            'name', 'slug', 'sku',
            'short_description', 'full_description',
            'price1', 'price2', 'price3',
            'option1', 'option2', 'option3', 'option4',
            'is_stock', 'stock_quantity',
            'home_delivery', 'pickup', 'partner_delivery', 'estimated_delivery_days',
            'status', 'featured', 'is_active',
            'active_price', 'promotion_discount', 'promotion_details',
            'average_rating', 'available_stock',
            'images', 'uploaded_images',  
            'created_at', 'updated_at', 'is_approve',
            'total_quantity_sold', 'total_discount',
        ]
        read_only_fields = [
            'id', 'vendor', 'slug', 'status', 'featured',
            'active_price', 'promotion_discount', 'promotion_details',
            'average_rating', 'available_stock',
            'created_at', 'updated_at', 'is_active', 'is_approve',
            'total_quantity_sold', 'total_discount',
        ]

    def get_total_quantity_sold(self, obj):
        return getattr(obj, 'total_quantity_sold', 0)

    def get_total_discount(self, obj):
        discount = getattr(obj, 'total_discount', None)
        return str(discount or Decimal('0.00'))

    def get_promotion_discount(self, obj):
        now = timezone.now()
        active_promos = obj.promotions.filter(
            is_active=True,
            start_datetime__lte=now,
            end_datetime__gte=now
        )
        if not active_promos.exists():
            return "0.00"

        base_price = obj.active_price or Decimal('0.00')
        max_discount = Decimal('0.00')
        for promo in active_promos:
            discounted_price = promo.calculate_discounted_price(base_price)
            discount_amount = base_price - discounted_price
            if discount_amount > max_discount:
                max_discount = discount_amount
        return str(max_discount)

    def get_promotion_details(self, obj):
        now = timezone.now()
        active_promos = obj.promotions.filter(is_active=True, start_datetime__lte=now, end_datetime__gte=now)
        if not active_promos.exists():
            return None

        base_price = obj.active_price or Decimal('0.00')
        best_promo = None
        max_discount = Decimal('0.00')
        for promo in active_promos:
            discounted_price = promo.calculate_discounted_price(base_price)
            discount_amount = base_price - discounted_price
            if discount_amount > max_discount:
                max_discount = discount_amount
                best_promo = promo

        if best_promo:
            return {
                "id": best_promo.id,
                "name": best_promo.name,
                "discount_type": best_promo.discount_type,
                "discount_value": str(best_promo.discount_value),
                "discount_amount": str(max_discount),
                "start_datetime": best_promo.start_datetime,
                "end_datetime": best_promo.end_datetime,
                "status": best_promo.status,
            }
        return None

    def get_active_price(self, obj):
        base_price = obj.active_price or Decimal('0.00')
        discount = Decimal(self.get_promotion_discount(obj))
        return str(max(base_price - discount, Decimal('0.00')))

    def validate(self, attrs):
        price_fields = [attrs.get("price1"), attrs.get("price2"), attrs.get("price3")]
        if not any(p is not None for p in price_fields):
            raise serializers.ValidationError({"price1": "At least one price must be set."})

        if attrs.get("is_stock", True) and attrs.get("stock_quantity", 0) < 0:
            raise serializers.ValidationError({"stock_quantity": "Stock quantity cannot be negative."})

        delivery_fields = ["home_delivery", "partner_delivery", "pickup"]
        if any(attrs.get(f) for f in delivery_fields) and attrs.get("estimated_delivery_days") is None:
            raise serializers.ValidationError({
                "estimated_delivery_days": "Must set estimated delivery days when delivery/pickup is enabled."
            })
        return attrs

    def create(self, validated_data):
        categories = validated_data.pop("categories", [])
        tags = validated_data.pop("tags", [])
        uploaded_images = validated_data.pop("uploaded_images", [])

        product = super().create(validated_data)

        if categories:
            product.categories.set(categories)
        if tags:
            product.tags.set(tags)

        for image in uploaded_images:
            ProductImage.objects.create(product=product, image=image)

        return product
    
    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        tags = validated_data.pop("tags", None)
        uploaded_images = validated_data.pop("uploaded_images", [])

        product = super().update(instance, validated_data)

        if categories is not None:
            product.categories.set(categories)
        if tags is not None:
            product.tags.set(tags)

        for image in uploaded_images:
            ProductImage.objects.create(product=product, image=image)

        return product



class VendorProductSerializer(serializers.ModelSerializer):
    prod_id = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()
    categories = serializers.StringRelatedField(many=True, read_only=True)
    price = serializers.DecimalField(source='active_price', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'prod_id',
            'name',
            'image',
            'categories',
            'price',
            'stock_quantity',
            'status',
        ]
        read_only_fields = ['prod_id', 'name', 'image', 'categories', 'price', 'stock_quantity', 'status']

    def get_image(self, obj):
        primary_img = obj.images.filter(is_primary=True).first()
        if primary_img:
            return primary_img.image.url
        return None


class ReturnProductSerializer(serializers.ModelSerializer):
    requested_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    uploaded_images = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=False,
        queryset=ImageUpload.objects.all(),
        required=False
    )
    status = serializers.CharField(read_only=True)

    class Meta:
        model = ReturnProduct
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")

        # restrict order_item dropdown for customers
        if request and hasattr(request, "user"):
            user = request.user
            if getattr(user, "role", None) == UserRole.CUSTOMER.value:
                self.fields["order_item"].queryset = OrderItem.objects.filter(
                    order__customer=user,
                    status=OrderStatus.DELIVERED.value  # এখন ঠিক আছে
                )

    def validate(self, data):
        user = self.context["request"].user
        order_item = data.get("order_item")

        if not order_item:
            raise serializers.ValidationError({"order_item": "Order is required."})

        # Ensure only customers can request returns
        if getattr(user, "role", None) != UserRole.CUSTOMER.value:
            raise serializers.ValidationError("Only customers can request product returns.")

        # Ensure the order item belongs to this customer
        if order_item.order.customer != user:
            raise serializers.ValidationError("You can only return products from your own orders.")

        # Ensure only delivered items can be returned
        if order_item.status != OrderStatus.DELIVERED.value:
            raise serializers.ValidationError(
                {"order_item": "You can only return products from delivered orders."}
            )

        # Limit to 5 images
        images = data.get("uploaded_images", [])
        if len(images) > 5:
            raise serializers.ValidationError({"uploaded_images": "Maximum 5 images allowed."})

        return data
