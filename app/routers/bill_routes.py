from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from ..deps import get_db, get_current_user
from ..reminders import send_email, check_and_send_bill_reminders

router = APIRouter(prefix="/bills", tags=["Bills"])

@router.post("/", response_model=schemas.BillRead)
def create_bill(
    bill_in: schemas.BillCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not (1 <= bill_in.due_day <= 31):
        raise HTTPException(status_code=400, detail="due_day must be between 1 and 31")

    bill = models.Bill(
        user_id=current_user.id,
        name=bill_in.name,
        amount=bill_in.amount,
        due_day=bill_in.due_day,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill

@router.get("/", response_model=List[schemas.BillRead])
def list_bills(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    bills = (
        db.query(models.Bill)
        .filter(models.Bill.user_id == current_user.id, models.Bill.is_active == True)
        .order_by(models.Bill.due_day.asc())
        .all()
    )
    return bills


@router.delete("/{bill_id}")
def delete_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    bill = (
        db.query(models.Bill)
        .filter(models.Bill.id == bill_id, models.Bill.user_id == current_user.id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    db.delete(bill)
    db.commit()
    return {"message": "Bill deleted"}

@router.get("/test-email")
def test_email(
    current_user: models.User = Depends(get_current_user),
):
    """
    Send a test email to the currently logged-in user.
    Use this to verify that SMTP + app password are set up correctly.
    """
    send_email(
        to_email=current_user.email,
        subject="Test Email from Wallet App",
        body="If you see this, your bill reminder email setup is working! 🎉",
    )
    return {"message": "Test email sent to your address"}

