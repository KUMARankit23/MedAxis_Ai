"""Billing Service — business logic."""
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Invoice, InvoiceItem, Prescription, InvoiceStatus, PaymentMethod
from app.schemas import InvoiceCreate, PrescriptionCreate
from app.config import INVENTORY_URL

GST_SLABS = {"OTC": 0.05, "PRESCRIPTION": 0.05, "CONTROLLED": 0.05,
             "SUPPLEMENT": 0.12, "EQUIPMENT": 0.12}

async def _next_invoice_number(db: AsyncSession) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    result = await db.execute(select(Invoice).where(Invoice.invoice_number.like(f"INV-{today}-%")))
    count = len(result.scalars().all())
    return f"INV-{today}-{count + 1:04d}"

async def create_invoice(db: AsyncSession, data: InvoiceCreate, pharmacist_id: str) -> Invoice:
    invoice = Invoice(
        invoice_number=await _next_invoice_number(db),
        outlet_id=data.outlet_id, prescription_id=data.prescription_id,
        patient_name=data.patient_name, pharmacist_id=pharmacist_id,
        payment_method=data.payment_method, notes=data.notes, status=InvoiceStatus.draft,
    )
    db.add(invoice)
    await db.flush()

    subtotal = total_tax = 0.0
    for item in data.items:
        gst = GST_SLABS.get(item.category.upper(), 0.05)
        pre_tax = item.unit_price * item.quantity * (1 - item.discount_pct / 100)
        tax = pre_tax * gst
        subtotal += pre_tax; total_tax += tax
        db.add(InvoiceItem(
            invoice_id=invoice.id, medicine_id=item.medicine_id,
            medicine_name=item.medicine_name, quantity=item.quantity,
            unit_price=item.unit_price, discount_pct=item.discount_pct,
            gst_rate=gst, line_total=round(pre_tax + tax, 2),
            is_prescription_item=item.is_prescription_item,
        ))

    invoice.subtotal = round(subtotal, 2)
    invoice.discount = round(data.discount, 2)
    invoice.tax = round(total_tax, 2)
    invoice.total = round(subtotal - data.discount + total_tax, 2)
    await db.commit()
    await db.refresh(invoice)
    return invoice

async def confirm_invoice(db: AsyncSession, invoice_id, token: str) -> Invoice:
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice: raise LookupError("Invoice not found")
    if invoice.status != InvoiceStatus.draft:
        raise ValueError(f"Cannot confirm invoice in status: {invoice.status.value}")

    async with httpx.AsyncClient() as client:
        for item in invoice.items:
            resp = await client.post(
                f"{INVENTORY_URL}/inventory/deduct",
                json={"medicine_id": item.medicine_id, "outlet_id": invoice.outlet_id,
                      "quantity": item.quantity, "reference_id": str(invoice.id)},
                headers={"Authorization": f"Bearer {token}"}, timeout=10
            )
            if resp.status_code != 200:
                raise ValueError(f"Stock deduction failed: {resp.json().get('detail','unknown')}")

    invoice.status = InvoiceStatus.confirmed
    invoice.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)
    return invoice

async def create_prescription(db: AsyncSession, data: PrescriptionCreate, user_id: str) -> Prescription:
    rx = Prescription(**data.model_dump(), created_by=user_id)
    db.add(rx); await db.commit(); await db.refresh(rx)
    return rx
