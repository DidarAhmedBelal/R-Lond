from enum import Enum

class UserRole(Enum):
    ADMIN = "admin"
    VENDOR = "vendor"
    CUSTOMER = "customer"

    @classmethod
    def choices(cls):
        return [(role.value, role.name.title()) for role in cls]
