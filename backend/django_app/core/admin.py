from django.contrib import admin

from backend.django_app.core import models


class TimeStampedAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.Supplier)
class SupplierAdmin(TimeStampedAdmin):
    list_display = ("code", "name", "country", "email", "phone", "is_active")
    search_fields = ("code", "name", "email", "phone")
    list_filter = ("is_active", "country")
    ordering = ("code",)


@admin.register(models.Customer)
class CustomerAdmin(TimeStampedAdmin):
    list_display = ("code", "name", "country", "email", "phone", "is_active")
    search_fields = ("code", "name", "email", "phone")
    list_filter = ("is_active", "country")
    ordering = ("code",)


@admin.register(models.Material)
class MaterialAdmin(TimeStampedAdmin):
    list_display = ("material_code", "description", "unit_of_measure", "category", "is_active")
    search_fields = ("material_code", "description", "category")
    list_filter = ("is_active", "category", "unit_of_measure")
    ordering = ("material_code",)


@admin.register(models.Inventory)
class InventoryAdmin(TimeStampedAdmin):
    list_display = (
        "material",
        "warehouse_code",
        "stock_qty",
        "reserved_qty",
        "available_qty",
    )
    search_fields = ("material__material_code", "material__description", "warehouse_code")
    list_filter = ("warehouse_code",)
    autocomplete_fields = ("material",)

    @admin.display(description="Available Qty")
    def available_qty(self, obj):
        return obj.stock_qty - obj.reserved_qty


class PurchaseOrderItemInline(admin.TabularInline):
    model = models.PurchaseOrderItem
    extra = 0
    autocomplete_fields = ("material",)
    fields = ("line_number", "material", "order_qty", "commit_qty", "unit_price")


@admin.register(models.PurchaseOrder)
class PurchaseOrderAdmin(TimeStampedAdmin):
    list_display = ("po_number", "supplier", "order_date", "status", "created_at")
    search_fields = ("po_number", "supplier__code", "supplier__name")
    list_filter = ("status", "order_date", "supplier__country")
    date_hierarchy = "order_date"
    autocomplete_fields = ("supplier",)
    inlines = (PurchaseOrderItemInline,)
    ordering = ("-order_date", "po_number")


@admin.register(models.PurchaseOrderItem)
class PurchaseOrderItemAdmin(TimeStampedAdmin):
    list_display = (
        "purchase_order",
        "line_number",
        "material",
        "order_qty",
        "commit_qty",
        "unit_price",
    )
    search_fields = (
        "purchase_order__po_number",
        "material__material_code",
        "material__description",
    )
    list_filter = ("purchase_order__status", "material__category")
    autocomplete_fields = ("purchase_order", "material")
    ordering = ("purchase_order__po_number", "line_number")


class SalesOrderItemInline(admin.TabularInline):
    model = models.SalesOrderItem
    extra = 0
    autocomplete_fields = ("material",)
    fields = ("line_number", "material", "order_qty", "unit_price")


@admin.register(models.SalesOrder)
class SalesOrderAdmin(TimeStampedAdmin):
    list_display = ("so_number", "customer", "order_date", "status", "created_at")
    search_fields = ("so_number", "customer__code", "customer__name")
    list_filter = ("status", "order_date", "customer__country")
    date_hierarchy = "order_date"
    autocomplete_fields = ("customer",)
    inlines = (SalesOrderItemInline,)
    ordering = ("-order_date", "so_number")


@admin.register(models.SalesOrderItem)
class SalesOrderItemAdmin(TimeStampedAdmin):
    list_display = ("sales_order", "line_number", "material", "order_qty", "unit_price")
    search_fields = ("sales_order__so_number", "material__material_code", "material__description")
    list_filter = ("sales_order__status", "material__category")
    autocomplete_fields = ("sales_order", "material")
    ordering = ("sales_order__so_number", "line_number")


@admin.register(models.OrderSchedule)
class OrderScheduleAdmin(TimeStampedAdmin):
    list_display = (
        "id",
        "purchase_order_item",
        "sales_order_item",
        "scheduled_date",
        "scheduled_qty",
    )
    search_fields = (
        "purchase_order_item__purchase_order__po_number",
        "sales_order_item__sales_order__so_number",
    )
    list_filter = ("scheduled_date",)
    date_hierarchy = "scheduled_date"
    autocomplete_fields = ("purchase_order_item", "sales_order_item")
    ordering = ("scheduled_date",)


@admin.register(models.Shipment)
class ShipmentAdmin(TimeStampedAdmin):
    list_display = ("shipment_number", "sales_order", "shipped_date", "shipped_qty", "carrier")
    search_fields = ("shipment_number", "sales_order__so_number", "carrier")
    list_filter = ("carrier", "shipped_date")
    date_hierarchy = "shipped_date"
    autocomplete_fields = ("sales_order",)
    ordering = ("-shipped_date", "shipment_number")


@admin.register(models.Invoice)
class InvoiceAdmin(TimeStampedAdmin):
    list_display = ("invoice_number", "sales_order", "invoice_date", "total_amount", "currency")
    search_fields = ("invoice_number", "sales_order__so_number")
    list_filter = ("currency", "invoice_date")
    date_hierarchy = "invoice_date"
    autocomplete_fields = ("sales_order",)
    ordering = ("-invoice_date", "invoice_number")


class ChatMessageInline(admin.TabularInline):
    model = models.ChatMessage
    extra = 0
    fields = ("role", "content", "metadata", "created_at")
    readonly_fields = ("created_at",)


@admin.register(models.ChatSession)
class ChatSessionAdmin(TimeStampedAdmin):
    list_display = ("session_id", "user", "title", "is_active", "created_at")
    search_fields = ("session_id", "user__username", "user__email", "title")
    list_filter = ("is_active", "created_at")
    autocomplete_fields = ("user",)
    inlines = (ChatMessageInline,)
    ordering = ("-created_at",)


@admin.register(models.ChatMessage)
class ChatMessageAdmin(TimeStampedAdmin):
    list_display = ("session", "role", "short_content", "created_at")
    search_fields = ("session__session_id", "content")
    list_filter = ("role", "created_at")
    autocomplete_fields = ("session",)
    ordering = ("-created_at",)

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:80]


@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "entity_type", "entity_id", "ip_address")
    search_fields = ("user__username", "user__email", "action", "entity_type", "entity_id")
    list_filter = ("action", "entity_type", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)
