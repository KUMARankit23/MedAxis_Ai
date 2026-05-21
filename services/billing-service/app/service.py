"""Billing Service — business logic."""
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Invoice, InvoiceItem, Prescription, InvoiceStatus, PaymentMethod
from app.schemas import InvoiceCreate, PrescriptionCreate
from app.config import INVENTORY_URL

# ── Prometheus custom counters ────────────────────────────────────────────────
try:
    from prometheus_client import Counter, REGISTRY

    def _counter(name, doc):
        # Avoid duplicate registration when module is reloaded in tests
        try:
            return Counter(name, doc)
        except ValueError:
            return REGISTRY._names_to_collectors.get(name + "_total") or Counter.__new__(Counter)

    INVOICES_CREATED   = _counter("medaxis_invoices_created",   "Total invoices created (draft)")
    INVOICES_CONFIRMED = _counter("medaxis_invoices_confirmed", "Total invoices confirmed")
    INVOICES_REFUNDED  = _counter("medaxis_invoices_refunded",  "Total invoices refunded")
except ImportError:
    class _Noop:
        def inc(self, *a, **kw): pass
    INVOICES_CREATED = INVOICES_CONFIRMED = INVOICES_REFUNDED = _Noop()

GST_SLABS = {"OTC": 0.05, "PRESCRIPTION": 0.05, "CONTROLLED": 0.05,
             "SUPPLEMENT": 0.12, "EQUIPMENT": 0.12}

async def _next_invoice_number(db: AsyncSession) -> str:
    """
    Generate a unique invoice number using a PostgreSQL sequence to avoid
    race conditions under concurrent requests, with an SQLite fallback for tests.
    """
    from sqlalchemy import text, func
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    
    if db.bind and db.bind.dialect.name == "sqlite":
        result = await db.execute(select(func.count(Invoice.id)))
        count = (result.scalar() or 0) + 1
        return f"INV-{today}-{count:06d}"

    # Create sequence on first use (idempotent)
    await db.execute(text(
        "CREATE SEQUENCE IF NOT EXISTS invoice_seq START 1 INCREMENT 1"
    ))
    result = await db.execute(text("SELECT nextval('invoice_seq')"))
    seq = result.scalar()
    return f"INV-{today}-{seq:06d}"

async def create_invoice(db: AsyncSession, data: InvoiceCreate, pharmacist_id: str) -> Invoice:
    from sqlalchemy.orm import selectinload
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

    # Re-fetch with items eagerly loaded to avoid MissingGreenlet on serialization
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice.id)
    )
    INVOICES_CREATED.inc()
    return result.scalar_one()

async def confirm_invoice(db: AsyncSession, invoice_id, token: str) -> Invoice:
    from sqlalchemy.orm import selectinload
    import uuid
    if isinstance(invoice_id, str):
        try:
            invoice_id = uuid.UUID(invoice_id)
        except ValueError:
            pass
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
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

    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice.id)
    )
    INVOICES_CONFIRMED.inc()
    return result.scalar_one()

async def create_prescription(db: AsyncSession, data: PrescriptionCreate, user_id: str) -> Prescription:
    rx = Prescription(**data.model_dump(), created_by=user_id)
    db.add(rx); await db.commit(); await db.refresh(rx)
    return rx


async def refund_invoice(db: AsyncSession, invoice_id: str, token: str) -> Invoice:
    """Refund a confirmed invoice and restore stock via inventory service."""
    import logging
    from sqlalchemy.orm import selectinload
    from datetime import date, timedelta
    import uuid
    if isinstance(invoice_id, str):
        try:
            invoice_id = uuid.UUID(invoice_id)
        except ValueError:
            pass

    logger = logging.getLogger(__name__)

    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise LookupError("Invoice not found")
    if invoice.status != InvoiceStatus.confirmed:
        raise ValueError(f"Only CONFIRMED invoices can be refunded (current: {invoice.status.value})")

    # Restore stock by creating a new batch for each returned line item.
    # We use /inventory/batches (receive) rather than /inventory/adjust because
    # we don't have a specific batch_id to adjust against at refund time.
    async with httpx.AsyncClient() as client:
        for item in invoice.items:
            resp = await client.post(
                f"{INVENTORY_URL}/inventory/batches",
                json={
                    "medicine_id": item.medicine_id,
                    "batch_number": f"REFUND-{invoice.invoice_number}-{str(item.id)[:6].upper()}",
                    "outlet_id": invoice.outlet_id,
                    "quantity": item.quantity,
                    # Returned stock gets a 1-year expiry as a safe default
                    "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            # Non-fatal: log but don't block the refund if stock restore fails
            if resp.status_code not in (200, 201):
                logger.warning(
                    f"Stock restore failed for {item.medicine_id}: {resp.text}"
                )

    invoice.status = InvoiceStatus.refunded
    await db.commit()
    await db.refresh(invoice)
    INVOICES_REFUNDED.inc()
    return invoice
