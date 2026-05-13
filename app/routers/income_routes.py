from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from ..deps import get_db, get_current_user

router = APIRouter(prefix="/income", tags=["Income"])


@router.post("/", response_model=schemas.IncomeRead)
def add_income(
    income_in: schemas.IncomeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    income = models.Income(
        user_id=current_user.id,
        source=income_in.source,
        amount=income_in.amount,
        date=income_in.date
    )
    db.add(income)
    db.commit()
    db.refresh(income)
    return income


@router.get("/", response_model=List[schemas.IncomeRead])
def get_incomes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Income)
        .filter(models.Income.user_id == current_user.id)
        .order_by(models.Income.date.desc())
        .all()
    )


@router.delete("/{income_id}")
def delete_income(
    income_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    income = (
        db.query(models.Income)
        .filter(models.Income.id == income_id, models.Income.user_id == current_user.id)
        .first()
    )
    if not income:
        raise HTTPException(status_code=404, detail="Income not found")

    db.delete(income)
    db.commit()
    return {"message": "Income deleted"}
