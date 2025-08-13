
from rest_framework import serializers
from common.models import Category, Tag, SEO, SavedProduct, Review
from products.models import Product
from users.serializers import UserPublicSerializer
from orders.models import Order, OrderItem, ShippingAddress

# -------------------
# Category
# -------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_name(self, value):
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value


# -------------------
# Tag
# -------------------
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_name(self, value):
        qs = Tag.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Tag with this name already exists.")
        return value


# -------------------
# SEO
# -------------------
class SEOSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEO
        fields = ['id', 'title', 'meta_description']


# -------------------
# Product
# -------------------
class ProductSerializer(serializers.ModelSerializer):
    vendor = UserPublicSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, source='tags', write_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'vendor', 'name', 'description', 'price',
            'is_stock', 'stock_quantity', 'category', 'category_id',
            'tags', 'tag_ids', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor', 'created_at', 'updated_at']

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        validated_data['vendor'] = self.context['request'].user
        product = super().create(validated_data)
        product.tags.set(tags)
        return product

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        instance = super().update(instance, validated_data)
        if tags is not None:
            instance.tags.set(tags)
        return instance


# -------------------
# SavedProduct
# -------------------
class SavedProductSerializer(serializers.ModelSerializer):
    vendor = UserPublicSerializer(read_only=True)

    class Meta:
        model = SavedProduct
        fields = [
            'id', 'vendor', 'name', 'data', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['vendor'] = self.context['request'].user
        return super().create(validated_data)


# -------------------
# Review
# -------------------
class ReviewSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'product', 'product_name', 'user', 'rating', 'comment',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)



class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    total = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2, read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_id',
            'order_date',
            'total',
            'payment_method_display',
            'order_status_display',
            'customer_name',
            'vendor_name',
        ]

    def get_customer_name(self, obj):
        user = obj.customer
        if user:
            full_name = getattr(user, 'get_full_name', None)
            if callable(full_name):
                name = full_name()
                if name:
                    return name
            name = (user.first_name + " " + user.last_name).strip()
            if name:
                return name
            return getattr(user, 'email', 'Unknown Customer')
        return None

    def get_vendor_name(self, obj):
        user = obj.vendor
        if user:
            full_name = getattr(user, 'get_full_name', None)
            if callable(full_name):
                name = full_name()
                if name:
                    return name
            name = (user.first_name + " " + user.last_name).strip()
            if name:
                return name
            return getattr(user, 'email', 'Unknown Vendor')
        return None




