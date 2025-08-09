from enum import Enum

class ProductStatus(Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    ARCHIVED = "archived"

    @classmethod
    def choices(cls):
        return [(status.value, status.name.title()) for status in cls]


class StockStatus(Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    LIMITED = "limited"

    @classmethod
    def choices(cls):
        return [(status.value, status.name.replace("_", " ").title()) for status in cls]
