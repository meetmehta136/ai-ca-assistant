from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.base import Invoice, GSTLedger, User
from datetime import datetime

router = APIRouter(prefix="/api", tags=["Dashboard API"])


@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    try:
        period = datetime.now().strftime("%Y-%m")

        itc_row = db.query(func.sum(GSTLedger.itc_available)).filter(
            GSTLedger.period == period
        ).scalar() or 0

        total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
        pending_invoices = db.query(func.count(Invoice.id)).filter(
            Invoice.status == "pending"
        ).scalar() or 0

        total_users = db.query(func.count(User.id)).scalar() or 0

        return {
            "total_itc": round(float(itc_row), 2),
            "total_invoices": total_invoices,
            "pending_invoices": pending_invoices,
            "total_clients": total_users,
            "period": period
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/clients")
def get_clients(db: Session = Depends(get_db)):
    try:
        period = datetime.now().strftime("%Y-%m")
        users = db.query(User).all()
        result = []

        for user in users:
            ledger = db.query(GSTLedger).filter(
                GSTLedger.user_id == user.id,
                GSTLedger.period == period
            ).first()

            invoice_count = db.query(func.count(Invoice.id)).filter(
                Invoice.user_id == user.id
            ).scalar() or 0

            itc = float(ledger.itc_available) if ledger else 0

            if itc > 1000:
                status = "compliant"
            elif itc > 0:
                status = "attention"
            else:
                status = "at-risk"

            risk_score = min(100, int((itc / 500) * 10 + invoice_count * 5))

            result.append({
                "id": str(user.id),
                "name": user.business_name or "Unknown",
                "gstin": user.gstin or "",
                "state": user.state_code or "",
                "whatsapp": user.phone or "",
                "itcThisMonth": itc,
                "invoiceCount": invoice_count,
                "complianceStatus": status,
                "riskScore": min(risk_score, 100)
            })

        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/clients/{client_id}")
def get_client_detail(client_id: int, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == client_id).first()
        if not user:
            return {"error": "Client not found"}

        invoices = db.query(Invoice).filter(Invoice.user_id == client_id).all()
        period = datetime.now().strftime("%Y-%m")
        ledger = db.query(GSTLedger).filter(
            GSTLedger.user_id == client_id,
            GSTLedger.period == period
        ).first()

        invoice_list = []
        for inv in invoices:
            itc = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
            total = float((inv.taxable_amt or 0) + itc)
            invoice_list.append({
                "id": str(inv.id),
                "invoiceNo": inv.invoice_no or "",
                "date": str(inv.date or ""),
                "supplierGstin": inv.seller_gstin or "",
                "taxableAmt": float(inv.taxable_amt or 0),
                "total": total,
                "cgst": float(inv.cgst or 0),
                "sgst": float(inv.sgst or 0),
                "igst": float(inv.igst or 0),
                "itc": itc,
                "status": inv.status or "confirmed",
                "aiCategory": "General"
            })

        return {
            "id": str(user.id),
            "name": user.business_name or "Unknown",
            "gstin": user.gstin or "",
            "state": user.state_code or "",
            "whatsapp": user.phone or "",
            "itcThisMonth": float(ledger.itc_available) if ledger else 0,
            "invoiceCount": len(invoices),
            "invoices": invoice_list
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/invoices")
def get_invoices(db: Session = Depends(get_db)):
    try:
        invoices = db.query(Invoice).order_by(Invoice.id.desc()).all()
        result = []
        for inv in invoices:
            user = db.query(User).filter(User.id == inv.user_id).first()
            itc = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
            total = float((inv.taxable_amt or 0) + itc)
            result.append({
                "id": str(inv.id),
                "clientId": str(inv.user_id),
                "clientName": user.business_name if user else "Unknown",
                "invoiceNo": inv.invoice_no or "",
                "date": str(inv.date or ""),
                "supplierGstin": inv.seller_gstin or "",
                "taxableAmt": float(inv.taxable_amt or 0),
                "total": total,
                "cgst": float(inv.cgst or 0),
                "sgst": float(inv.sgst or 0),
                "igst": float(inv.igst or 0),
                "itc": itc,
                "status": inv.status or "confirmed",
                "aiCategory": "General"
            })
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(invoice_id: int, db: Session = Depends(get_db)):
    try:
        inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not inv:
            return {"error": "Invoice not found"}
        inv.status = "confirmed"
        db.commit()
        return {"success": True, "invoice_id": invoice_id, "status": "confirmed"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/invoices/{invoice_id}/reject")
def reject_invoice(invoice_id: int, db: Session = Depends(get_db)):
    try:
        inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not inv:
            return {"error": "Invoice not found"}
        inv.status = "rejected"
        db.commit()
        return {"success": True, "invoice_id": invoice_id, "status": "rejected"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    try:
        users = db.query(User).all()
        alerts = []
        period = datetime.now().strftime("%Y-%m")

        for user in users:
            invoice_count = db.query(func.count(Invoice.id)).filter(
                Invoice.user_id == user.id
            ).scalar() or 0

            if invoice_count == 0:
                alerts.append({
                    "id": f"alert-{user.id}",
                    "clientName": user.business_name or "Unknown",
                    "type": "No Invoices",
                    "message": "No invoices uploaded this month. ITC at risk.",
                    "priority": "high",
                    "dueDate": f"{period}-20",
                    "daysRemaining": 11,
                    "resolved": False
                })
            elif invoice_count < 3:
                alerts.append({
                    "id": f"alert-low-{user.id}",
                    "clientName": user.business_name or "Unknown",
                    "type": "Low Invoice Count",
                    "message": f"Only {invoice_count} invoice(s) uploaded. More expected.",
                    "priority": "medium",
                    "dueDate": f"{period}-25",
                    "daysRemaining": 16,
                    "resolved": False
                })

        return alerts
    except Exception as e:
        return {"error": str(e)}