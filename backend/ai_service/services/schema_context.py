DATABASE_SCHEMA_CONTEXT = """
Allowed reporting tables and columns:

- suppliers(id, code, name, email, phone, country, is_active, created_at, updated_at)
- customers(id, code, name, email, phone, country, is_active, created_at, updated_at)
- materials(
    id, material_code, description, unit_of_measure, category, is_active, created_at, updated_at
  )
- inventory(id, material_id, stock_qty, reserved_qty, warehouse_code, created_at, updated_at)
- purchase_orders(id, po_number, supplier_id, order_date, status, created_at, updated_at)
- purchase_order_items(
    id, purchase_order_id, material_id, line_number, order_qty, commit_qty, unit_price,
    created_at, updated_at
  )
- sales_orders(id, so_number, customer_id, order_date, status, created_at, updated_at)
- sales_order_items(
    id, sales_order_id, material_id, line_number, order_qty, unit_price, created_at, updated_at
  )
- order_schedule(
    id, purchase_order_item_id, sales_order_item_id, scheduled_date, scheduled_qty,
    created_at, updated_at
  )
- shipment(
    id, shipment_number, sales_order_id, shipped_date, shipped_qty, carrier,
    created_at, updated_at
  )
- invoice(
    id, invoice_number, sales_order_id, invoice_date, total_amount, currency,
    created_at, updated_at
  )

Required join keys:
- purchase_orders.supplier_id = suppliers.id
- purchase_order_items.purchase_order_id = purchase_orders.id
- purchase_order_items.material_id = materials.id
- inventory.material_id = materials.id
- sales_orders.customer_id = customers.id
- sales_order_items.sales_order_id = sales_orders.id
- sales_order_items.material_id = materials.id
- order_schedule.purchase_order_item_id = purchase_order_items.id
- order_schedule.sales_order_item_id = sales_order_items.id
- shipment.sales_order_id = sales_orders.id
- invoice.sales_order_id = sales_orders.id

Never use non-existent columns such as po_id, so_id, supplier_code_id, customer_code_id,
material_code_id, or material.

Business interpretation rules:
- Customer codes look like CUST00003 and are stored in customers.code.
- Supplier codes look like SUP0001 and are stored in suppliers.code.
- Purchase order numbers look like PO1001 and are stored in purchase_orders.po_number.
- Sales order numbers look like SO1001 and are stored in sales_orders.so_number.
- Material codes look like MAT0100 and are stored in materials.material_code.
- For questions about what a customer ordered, use sales_orders, sales_order_items, customers,
  and materials.
- For customer order quantity, committed quantity, booked quantity, or ordered quantity, use
  sales_order_items.order_qty because customers do not have purchase_order_items.commit_qty.
- Use purchase_order_items.commit_qty only for supplier or purchase order commitment questions.
- Never reference purchase_order_items.commit_qty unless purchase_order_items is explicitly joined.
""".strip()
