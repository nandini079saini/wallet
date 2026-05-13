from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str



class UserRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ---------- Expense ----------
class ExpenseBase(BaseModel):
    amount: float
    currency: str = "INR"
    category: Optional[str] = None
    date: date
    description: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseRead(ExpenseBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- BILLS ----------

class BillBase(BaseModel):
    name: str
    amount: float
    due_day: int   # 1–31, e.g. 5 = 5th of every month


class BillCreate(BillBase):
    pass


class BillRead(BillBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ---------- INCOME ----------
class IncomeBase(BaseModel):
    source: str
    amount: float
    date: date

class IncomeCreate(IncomeBase):
    pass

class IncomeRead(IncomeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

