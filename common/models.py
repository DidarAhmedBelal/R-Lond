from users.models import BaseModel
from django.db import models
from django.utils.text import slugify
import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from common.enums import SavedProductStatus

User = settings.AUTH_USER_MODEL


class Category(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["name"])]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or str(uuid.uuid4())[:8]
            slug = base
            i = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Tag(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["name"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or str(uuid.uuid4())[:8]
            slug = base
            i = 1
            while Tag.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class SEO(models.Model):
    title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    def __str__(self):
        return self.title or "SEO Settings"


class SavedProduct(BaseModel):
    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_products",
        limit_choices_to={"role": "vendor"},
    )
    name = models.CharField(max_length=255, blank=True)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30,
        choices=SavedProductStatus.choices(),
        default=SavedProductStatus.DRAFT.value,
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["vendor"])]

    def __str__(self):
        return self.name or f"Draft #{self.pk}"


class Review(BaseModel):
    product = models.ForeignKey(
        "products.Product",  # String reference to avoid import
        on_delete=models.CASCADE,
        related_name="reviews"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="product_reviews")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("product", "user")
        indexes = [models.Index(fields=["product", "user"])]

    def __str__(self):
        return f"Review by {getattr(self.user, 'email', self.user)} for {self.product.name}"


class CartItem(BaseModel):
    product = models.ForeignKey(
        "products.Product",  # String reference to avoid import
        on_delete=models.CASCADE,
        related_name="cart_items"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user"]), models.Index(fields=["product"])]
        unique_together = ("product", "user")

    def __str__(self):
        return f"{self.quantity} × {self.product.name} for {getattr(self.user, 'email', self.user)}"

    @property
    def subtotal(self):
        return (self.price_snapshot or Decimal("0.00")) * Decimal(self.quantity)

    def clean(self):
        if self.product.is_stock and self.quantity > self.product.stock_quantity:
            raise ValidationError({"quantity": "Requested quantity exceeds available stock."})
