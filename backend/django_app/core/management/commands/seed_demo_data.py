import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from backend.django_app.core.models import (
    AuditLog,
    Customer,
    Inventory,
    Invoice,
    Material,
    OrderSchedule,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesOrder,
    SalesOrderItem,
    Shipment,
    Supplier,
)


class Command(BaseCommand):
    help = "Seed realistic demo business data for local chatbot development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo business data before seeding.",
        )
        parser.add_argument(
            "--purchase-orders",
            type=int,
            default=2600,
            help="Number of purchase orders to create.",
        )
        parser.add_argument(
            "--sales-orders",
            type=int,
            default=3000,
            help="Number of sales orders to create.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)

        if options["reset"]:
            self._reset_data()

        if Supplier.objects.exists() or Customer.objects.exists() or Material.objects.exists():
            self.stdout.write(
                self.style.WARNING("Demo data already exists. Use --reset to recreate it.")
            )
            return

        user = self._get_or_create_demo_user()
        suppliers = self._create_suppliers()
        customers = self._create_customers()
        materials = self._create_materials()
        self._create_inventory(materials)
        purchase_orders, purchase_items = self._create_purchase_orders(
            suppliers,
            materials,
            options["purchase_orders"],
        )
        sales_orders, sales_items = self._create_sales_orders(
            customers,
            materials,
            options["sales_orders"],
        )
        self._create_schedules(purchase_items, sales_items)
        self._create_shipments(sales_orders)
        self._create_invoices(sales_orders)
        self._create_audit_log(user)

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded demo data: "
                f"{len(suppliers)} suppliers, "
                f"{len(customers)} customers, "
                f"{len(materials)} materials, "
                f"{len(purchase_orders)} purchase orders, "
                f"{len(sales_orders)} sales orders."
            )
        )

    def _reset_data(self) -> None:
        AuditLog.objects.all().delete()
        Invoice.objects.all().delete()
        Shipment.objects.all().delete()
        OrderSchedule.objects.all().delete()
        SalesOrderItem.objects.all().delete()
        SalesOrder.objects.all().delete()
        PurchaseOrderItem.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        Inventory.objects.all().delete()
        Material.objects.all().delete()
        Customer.objects.all().delete()
        Supplier.objects.all().delete()

    def _get_or_create_demo_user(self):
        user_model = get_user_model()
        user, _created = user_model.objects.get_or_create(
            username="demo_admin",
            defaults={
                "email": "demo_admin@example.com",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.email = "demo_admin@example.com"
        user.is_staff = True
        user.is_superuser = True
        user.set_password("DemoAdmin123!")
        user.save(update_fields=["email", "is_staff", "is_superuser", "password"])
        return user

    def _create_suppliers(self) -> list[Supplier]:
        countries = ["US", "IN", "DE", "JP", "SG", "GB", "CA"]
        suppliers = [
            Supplier(
                code=f"SUP{i:04d}",
                name=f"Supplier {i:04d}",
                email=f"supplier{i:04d}@example.com",
                phone=f"+1-555-{i:04d}",
                country=random.choice(countries),
            )
            for i in range(1, 81)
        ]
        return Supplier.objects.bulk_create(suppliers)

    def _create_customers(self) -> list[Customer]:
        countries = ["US", "IN", "DE", "JP", "SG", "GB", "CA", "AU"]
        customers = [
            Customer(
                code=f"CUST{i:05d}",
                name=f"Customer {i:05d}",
                email=f"customer{i:05d}@example.com",
                phone=f"+1-777-{i:05d}",
                country=random.choice(countries),
            )
            for i in range(1, 501)
        ]
        return Customer.objects.bulk_create(customers)

    def _create_materials(self) -> list[Material]:
        categories = ["RAW", "PACKAGING", "FINISHED", "SPARE", "SERVICE"]
        materials = [
            Material(
                material_code=f"MAT{i:04d}",
                description=f"Material {i:04d}",
                unit_of_measure=random.choice(["EA", "KG", "L", "BOX"]),
                category=random.choice(categories),
            )
            for i in range(1, 1001)
        ]
        return Material.objects.bulk_create(materials)

    def _create_inventory(self, materials: list[Material]) -> None:
        warehouses = ["MAIN", "EAST", "WEST", "NORTH", "SOUTH"]
        Inventory.objects.bulk_create(
            [
                Inventory(
                    material=material,
                    stock_qty=Decimal(random.randint(100, 20000)),
                    reserved_qty=Decimal(random.randint(0, 500)),
                    warehouse_code=random.choice(warehouses),
                )
                for material in materials
            ]
        )

    def _create_purchase_orders(
        self,
        suppliers: list[Supplier],
        materials: list[Material],
        order_count: int,
    ) -> tuple[list[PurchaseOrder], list[PurchaseOrderItem]]:
        today = timezone.localdate()
        statuses = list(PurchaseOrder.Status.values)
        purchase_orders = [
            PurchaseOrder(
                po_number=f"PO{1000 + i}",
                supplier=random.choice(suppliers),
                order_date=today - timedelta(days=random.randint(0, 180)),
                status=random.choice(statuses),
            )
            for i in range(1, order_count + 1)
        ]
        purchase_orders = PurchaseOrder.objects.bulk_create(purchase_orders)

        items = []
        for purchase_order in purchase_orders:
            for line_number in range(1, random.randint(2, 5)):
                order_qty = Decimal(random.randint(10, 5000))
                items.append(
                    PurchaseOrderItem(
                        purchase_order=purchase_order,
                        material=random.choice(materials),
                        line_number=line_number,
                        order_qty=order_qty,
                        commit_qty=Decimal(random.randint(0, int(order_qty))),
                        unit_price=Decimal(random.randint(5, 500)),
                    )
                )
        return purchase_orders, PurchaseOrderItem.objects.bulk_create(items)

    def _create_sales_orders(
        self,
        customers: list[Customer],
        materials: list[Material],
        order_count: int,
    ) -> tuple[list[SalesOrder], list[SalesOrderItem]]:
        today = timezone.localdate()
        statuses = list(SalesOrder.Status.values)
        sales_orders = [
            SalesOrder(
                so_number=f"SO{1000 + i}",
                customer=random.choice(customers),
                order_date=today - timedelta(days=random.randint(0, 180)),
                status=random.choice(statuses),
            )
            for i in range(1, order_count + 1)
        ]
        sales_orders = SalesOrder.objects.bulk_create(sales_orders)

        items = []
        for sales_order in sales_orders:
            for line_number in range(1, random.randint(2, 5)):
                items.append(
                    SalesOrderItem(
                        sales_order=sales_order,
                        material=random.choice(materials),
                        line_number=line_number,
                        order_qty=Decimal(random.randint(5, 3000)),
                        unit_price=Decimal(random.randint(10, 800)),
                    )
                )
        return sales_orders, SalesOrderItem.objects.bulk_create(items)

    def _create_schedules(
        self,
        purchase_items: list[PurchaseOrderItem],
        sales_items: list[SalesOrderItem],
    ) -> None:
        today = timezone.localdate()
        schedules = []
        for item in purchase_items[:5000]:
            schedules.append(
                OrderSchedule(
                    purchase_order_item=item,
                    scheduled_date=today + timedelta(days=random.randint(1, 90)),
                    scheduled_qty=max(Decimal("1"), item.commit_qty),
                )
            )
        for item in sales_items[:5000]:
            schedules.append(
                OrderSchedule(
                    sales_order_item=item,
                    scheduled_date=today + timedelta(days=random.randint(1, 90)),
                    scheduled_qty=item.order_qty,
                )
            )
        OrderSchedule.objects.bulk_create(schedules)

    def _create_shipments(self, sales_orders: list[SalesOrder]) -> None:
        today = timezone.localdate()
        carriers = ["DHL", "FedEx", "UPS", "BlueDart", "Maersk"]
        Shipment.objects.bulk_create(
            [
                Shipment(
                    shipment_number=f"SHP{1000 + index}",
                    sales_order=sales_order,
                    shipped_date=today - timedelta(days=random.randint(0, 120)),
                    shipped_qty=Decimal(random.randint(1, 2000)),
                    carrier=random.choice(carriers),
                )
                for index, sales_order in enumerate(sales_orders[:1800], start=1)
            ]
        )

    def _create_invoices(self, sales_orders: list[SalesOrder]) -> None:
        today = timezone.localdate()
        Invoice.objects.bulk_create(
            [
                Invoice(
                    invoice_number=f"INV{1000 + index}",
                    sales_order=sales_order,
                    invoice_date=today - timedelta(days=random.randint(0, 120)),
                    total_amount=Decimal(random.randint(1000, 250000)),
                    currency="USD",
                )
                for index, sales_order in enumerate(sales_orders[:2200], start=1)
            ]
        )

    def _create_audit_log(self, user) -> None:
        AuditLog.objects.create(
            user=user,
            action="DEMO_DATA_SEEDED",
            entity_type="database",
            metadata={"source": "seed_demo_data"},
        )
