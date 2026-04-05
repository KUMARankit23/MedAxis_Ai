from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.database import get_db
from app.models import Invoice, InvoiceStatus
from app.schemas import InvoiceCreate, InvoiceResponse, PrescriptionCreate, PrescriptionResponse
from app.service import create_invoice, confirm_invoice, create_prescription
from app.config import JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt

router = APIRouter()

def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): raise HTTPException(401, "Missing token")
    try:
        p = pyjwt.decode(auth.split(" ",1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if p.get("type") != "access": raise HTTPException(401, "Invalid token type")
        return p
    except pyjwt.ExpiredSignatureError: raise HTTPException(401, "Token expired")
    except pyjwt.InvalidTokenError: raise HTTPException(401, "Invalid token")

def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user.get("role") not in roles: raise HTTPException(403, f"Required: {list(roles)}")
        return user
    return dep

@router.post("/billing/prescriptions", response_model=PrescriptionResponse, status_code=201, tags=["Prescriptions"])
async def add_prescription(body: PrescriptionCreate, user=Depends(require_role("admin","pharmacist")), db: AsyncSession=Depends(get_db)):
    return await create_prescription(db, body, user["sub"])

@router.post("/billing/invoices", response_model=InvoiceResponse, status_code=201, tags=["Invoices"])
async def create(body: InvoiceCreate, user=Depends(require_role("admin","pharmacist")), db: AsyncSession=Depends(get_db)):
    return await create_invoice(db, body, user["sub"])

@router.post("/billing/invoices/{invoice_id}/confirm", response_model=InvoiceResponse, tags=["Invoices"])
async def confirm(invoice_id: str, request: Request, user=Depends(require_role("admin","pharmacist")), db: AsyncSession=Depends(get_db)):
    token = request.headers.get("Authorization","").split(" ",1)[-1]
    try: return await confirm_invoice(db, invoice_id, token)
    except LookupError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(409, str(e))

@router.post("/billing/invoices/{invoice_id}/cancel", tags=["Invoices"])
async def cancel(invoice_id: str, user=Depends(require_role("admin","supervisor")), db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalar_one_or_none()
    if not inv: raise HTTPException(404, "Invoice not found")
    if inv.status == InvoiceStatus.confirmed: raise HTTPException(400, "Use refund for confirmed invoices")
    inv.status = InvoiceStatus.cancelled
    await db.commit()
    return {"message": "Invoice cancelled"}

@router.post("/billing/invoices/{invoice_id}/refund", tags=["Invoices"])
async def refund(invoice_id: str, user=Depends(require_role("admin","supervisor")), db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalar_one_or_none()
    if not inv: raise HTTPException(404, "Invoice not found")
    if inv.status != InvoiceStatus.confirmed: raise HTTPException(400, "Only CONFIRMED invoices can be refunded")
    inv.status = InvoiceStatus.refunded
    await db.commit()
    return {"message": "Invoice refunded", "refunded_amount": inv.total}

@router.get("/billing/invoices", response_model=List[InvoiceResponse], tags=["Invoices"])
async def list_invoices(outlet_id: Optional[str]=None, status: Optional[str]=None,
                         user=Depends(get_current_user), db: AsyncSession=Depends(get_db)):
    q = select(Invoice).order_by(Invoice.created_at.desc()).limit(100)
    if outlet_id: q = q.where(Invoice.outlet_id == outlet_id)
    if status: q = q.where(Invoice.status == status)
    result = await db.execute(q)
    return [InvoiceResponse.model_validate(i) for i in result.scalars().all()]

@router.get("/billing/invoices/{invoice_id}", response_model=InvoiceResponse, tags=["Invoices"])
async def get_invoice(invoice_id: str, user=Depends(get_current_user), db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalar_one_or_none()
    if not inv: raise HTTPException(404, "Invoice not found")
    return InvoiceResponse.model_validate(inv)
