from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Supplier(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "suppliers"
        indexes = [
            models.Index(fields=["code"], name="idx_suppliers_code"),
            models.Index(fields=["name"], name="idx_suppliers_name"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Customer(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "customers"
        indexes = [
            models.Index(fields=["code"], name="idx_customers_code"),
            models.Index(fields=["name"], name="idx_customers_name"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Material(TimeStampedModel):
    material_code = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255)
    unit_of_measure = models.CharField(max_length=20, default="EA")
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "materials"
        indexes = [
            models.Index(fields=["material_code"], name="idx_materials_code"),
            models.Index(fields=["category"], name="idx_materials_category"),
        ]

    def __str__(self) -> str:
        return self.material_code


class Inventory(TimeStampedModel):
    material = models.OneToOneField(Material, on_delete=models.PROTECT, related_name="inventory")
    stock_qty = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reserved_qty = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    warehouse_code = models.CharField(max_length=50, default="MAIN")

    class Meta:
        db_table = "inventory"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock_qty__gte=0),
                name="chk_inventory_stock_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_qty__gte=0),
                name="chk_inventory_reserved_gte_0",
            ),
        ]
        indexes = [
            models.Index(fields=["warehouse_code"], name="idx_inventory_warehouse"),
        ]


class PurchaseOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially Received"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    order_date = models.DateField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)

    class Meta:
        db_table = "purchase_orders"
        indexes = [
            models.Index(fields=["po_number"], name="idx_po_number"),
            models.Index(fields=["supplier", "order_date"], name="idx_po_supplier_date"),
            models.Index(fields=["status"], name="idx_po_status"),
        ]

    def __str__(self) -> str:
        return self.po_number


class PurchaseOrderItem(TimeStampedModel):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
    )
    line_number = models.PositiveIntegerField()
    order_qty = models.DecimalField(max_digits=14, decimal_places=3)
    commit_qty = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "purchase_order_items"
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "line_number"],
                name="uq_po_item_line",
            ),
            models.CheckConstraint(
                condition=models.Q(order_qty__gt=0),
                name="chk_poi_order_qty_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(commit_qty__gte=0),
                name="chk_poi_commit_qty_gte_0",
            ),
        ]
        indexes = [
            models.Index(fields=["purchase_order"], name="idx_poi_po"),
            models.Index(fields=["material"], name="idx_poi_material"),
        ]


class SalesOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        PARTIALLY_SHIPPED = "PARTIALLY_SHIPPED", "Partially Shipped"
        SHIPPED = "SHIPPED", "Shipped"
        CANCELLED = "CANCELLED", "Cancelled"

    so_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders")
    order_date = models.DateField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)

    class Meta:
        db_table = "sales_orders"
        indexes = [
            models.Index(fields=["so_number"], name="idx_so_number"),
            models.Index(fields=["customer", "order_date"], name="idx_so_customer_date"),
            models.Index(fields=["status"], name="idx_so_status"),
        ]

    def __str__(self) -> str:
        return self.so_number


class SalesOrderItem(TimeStampedModel):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="sales_order_items",
    )
    line_number = models.PositiveIntegerField()
    order_qty = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "sales_order_items"
        constraints = [
            models.UniqueConstraint(fields=["sales_order", "line_number"], name="uq_so_item_line"),
            models.CheckConstraint(
                condition=models.Q(order_qty__gt=0),
                name="chk_soi_order_qty_gt_0",
            ),
        ]
        indexes = [
            models.Index(fields=["sales_order"], name="idx_soi_so"),
            models.Index(fields=["material"], name="idx_soi_material"),
        ]


class OrderSchedule(TimeStampedModel):
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="schedules",
    )
    sales_order_item = models.ForeignKey(
        SalesOrderItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="schedules",
    )
    scheduled_date = models.DateField()
    scheduled_qty = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        db_table = "order_schedule"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(purchase_order_item__isnull=False, sales_order_item__isnull=True)
                    | models.Q(purchase_order_item__isnull=True, sales_order_item__isnull=False)
                ),
                name="chk_schedule_exactly_one_item",
            ),
            models.CheckConstraint(
                condition=models.Q(scheduled_qty__gt=0),
                name="chk_schedule_qty_gt_0",
            ),
        ]
        indexes = [
            models.Index(fields=["scheduled_date"], name="idx_schedule_date"),
        ]


class Shipment(TimeStampedModel):
    shipment_number = models.CharField(max_length=50, unique=True)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="shipments")
    shipped_date = models.DateField()
    shipped_qty = models.DecimalField(max_digits=14, decimal_places=3)
    carrier = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "shipment"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(shipped_qty__gt=0),
                name="chk_shipment_qty_gt_0",
            ),
        ]
        indexes = [
            models.Index(fields=["shipment_number"], name="idx_shipment_number"),
            models.Index(fields=["sales_order", "shipped_date"], name="idx_shipment_so_date"),
        ]


class Invoice(TimeStampedModel):
    invoice_number = models.CharField(max_length=50, unique=True)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="invoices")
    invoice_date = models.DateField()
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    class Meta:
        db_table = "invoice"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="chk_invoice_amount_gte_0",
            ),
        ]
        indexes = [
            models.Index(fields=["invoice_number"], name="idx_invoice_number"),
            models.Index(fields=["sales_order", "invoice_date"], name="idx_invoice_so_date"),
        ]


class ChatSession(TimeStampedModel):
    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "chat_sessions"
        indexes = [
            models.Index(fields=["user", "is_active"], name="idx_chat_session_user_active"),
            models.Index(fields=["session_id"], name="idx_chat_session_id"),
        ]


class ChatMessage(TimeStampedModel):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ASSISTANT = "ASSISTANT", "Assistant"
        SYSTEM = "SYSTEM", "System"
        TOOL = "TOOL", "Tool"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "chat_messages"
        indexes = [
            models.Index(fields=["session", "created_at"], name="idx_chat_msg_session_created"),
            models.Index(fields=["role"], name="idx_chat_msg_role"),
        ]


class AuditLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100, blank=True)
    entity_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "audit_logs"
        indexes = [
            models.Index(fields=["created_at"], name="idx_audit_created_at"),
            models.Index(fields=["user", "created_at"], name="idx_audit_user_created"),
            models.Index(fields=["action"], name="idx_audit_action"),
        ]
