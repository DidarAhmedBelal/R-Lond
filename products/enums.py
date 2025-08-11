from enum import Enum

class ProductStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"  
    REJECTED = "rejected"  
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"

    @classmethod
    def choices(cls):
        return [(key.value, key.name.title()) for key in cls]
