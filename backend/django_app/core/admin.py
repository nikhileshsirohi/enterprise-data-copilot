from django.contrib import admin

from backend.django_app.core import models


@admin.register(models.Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "country", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active", "country")


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "country", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active", "country")


@admin.register(models.Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("material_code", "description", "unit_of_measure", "category", "is_active")
    search_fields = ("material_code", "description")
    list_filter = ("is_active", "category")


admin.site.register(models.Inventory)
admin.site.register(models.PurchaseOrder)
admin.site.register(models.PurchaseOrderItem)
admin.site.register(models.SalesOrder)
admin.site.register(models.SalesOrderItem)
admin.site.register(models.OrderSchedule)
admin.site.register(models.Shipment)
admin.site.register(models.Invoice)
admin.site.register(models.ChatSession)
admin.site.register(models.ChatMessage)
admin.site.register(models.AuditLog)
