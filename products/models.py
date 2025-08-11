from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings
from decimal import Decimal
import uuid
from users.models import BaseModel
from products.enums import ProductStatus
from django.db.models import Avg

User = settings.AUTH_USER_MODEL


class Product(BaseModel):
    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products",
        limit_choices_to={"role": "vendor"},
    )

    # taxonomy - string references to avoid circular import
    categories = models.ManyToManyField("common.Category", related_name="products", blank=True)
    tags = models.ManyToManyField("common.Tag", related_name="products", blank=True)
    seo = models.ForeignKey("common.SEO", on_delete=models.SET_NULL, null=True, blank=True)

    # identity
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    sku = models.CharField(max_length=64, blank=True, null=True, help_text="Optional SKU for inventory")

    short_description = models.CharField(max_length=500, blank=True)
    full_description = models.TextField(blank=True)

    # pricing
    price1 = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    price2 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(Decimal('0.00'))])
    price3 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(Decimal('0.00'))])

    # inventory & variants
    option1 = models.CharField(max_length=100, blank=True)
    option2 = models.CharField(max_length=100, blank=True)
    option3 = models.CharField(max_length=100, blank=True)
    option4 = models.CharField(max_length=100, blank=True)

    is_stock = models.BooleanField(default=True)
    stock_quantity = models.PositiveIntegerField(default=0)

    # delivery
    home_delivery = models.BooleanField(default=False)
    pickup = models.BooleanField(default=False)
    partner_delivery = models.BooleanField(default=False)
    estimated_delivery_days = models.PositiveIntegerField(blank=True, null=True)

    # metadata
    status = models.CharField(
        max_length=30,
        choices=ProductStatus.choices(),
        default=ProductStatus.DRAFT.value
    )
    featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="General availability toggle")
    is_approve = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["vendor"]),
            models.Index(fields=["status", "is_active"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.price1 is None:
            raise ValidationError({"price1": "Primary price must be set."})
        if any(p is not None and p < Decimal('0.00') for p in [self.price1, self.price2, self.price3]):
            raise ValidationError("Prices must be non-negative.")

        if self.is_stock and (self.stock_quantity is None or self.stock_quantity < 0):
            raise ValidationError({"stock_quantity": "Stock quantity must be >= 0."})

        if (self.home_delivery or self.partner_delivery or self.pickup) and self.estimated_delivery_days is None:
            raise ValidationError({"estimated_delivery_days": "Set estimated_delivery_days when product supports delivery/pickup."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or str(uuid.uuid4())[:8]
            slug = base
            i = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def active_price(self):
        for price in (self.price1, self.price2, self.price3):
            if price is not None:
                return price
        return Decimal('0.00')

    @property
    def average_rating(self):
        agg = self.reviews.aggregate(avg=Avg('rating'))
        return agg['avg'] or 0

    @property
    def available_stock(self):
        return None if not self.is_stock else self.stock_quantity

    def get_absolute_url(self):
        try:
            return reverse("products:detail", args=[self.slug])
        except Exception:
            return f"/products/{self.slug}/"


class ProductImage(BaseModel):
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/%d/")
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False, help_text="Primary image used as thumbnail")

    class Meta:
        ordering = ["-is_primary", "-created_at"]
        indexes = [models.Index(fields=["product"])]

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
