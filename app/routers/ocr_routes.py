from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import re
import requests
import os
from datetime import datetime, date

from ..deps import get_db, get_current_user
from ..models import Expense

router = APIRouter(prefix="/ocr", tags=["OCR"])



# -----------------------------
# CATEGORY KEYWORDS
# -----------------------------

CATEGORY_KEYWORDS = {
    "Food": [
    "restaurant",
    "cafe",
    "pizza",
    "burger",
    "swiggy",
    "zomato",
    "food",
    "hotel",
    "dosa",
    "vada",
    "toast"],

    "Transport": [
        "uber", "ola", "metro", "taxi",
        "petrol", "fuel", "bus"
    ],

    "Shopping": [
        "amazon", "flipkart", "mall",
        "store", "shop"
    ],

    "Bills": [
        "electricity", "water", "wifi",
        "internet", "bill", "recharge"
    ],

    "Healthcare": [
        "hospital", "medical", "pharmacy",
        "doctor", "medicine"
    ],

    "Entertainment": [
        "movie", "netflix", "spotify",
        "cinema"
    ]
}

# -----------------------------
# OCR TEXT EXTRACTION
# -----------------------------

def extract_text(image_bytes: bytes) -> str:

    api_key = os.getenv("OCR_SPACE_API_KEY")
    if not api_key:
        raise Exception("OCR_SPACE_API_KEY missing in .env")

    response = requests.post(

        "https://api.ocr.space/parse/image",

        files={
            "filename": ("receipt.jpg", image_bytes)
        },

        data={
            "apikey": api_key,
            "language": "eng",
            "isOverlayRequired": False,
            "OCREngine": 2,
        },
        timeout=30,
    )

    result = response.json()

    if result.get("IsErroredOnProcessing"):
        raise Exception(
            result.get("ErrorMessage", "OCR failed")
        )

    parsed_results = result.get("ParsedResults")

    if not parsed_results:
        raise Exception("No OCR text detected")

    text = parsed_results[0].get("ParsedText", "")

    return text

# -----------------------------
# AMOUNT EXTRACTION
# -----------------------------

def parse_amount(text: str):

    lines = text.splitlines()

    # --------------------------------
    # PRIORITY 1:
    # "Total" line (excluding subtotal)
    # --------------------------------

    for line in lines:

        lower = line.lower().strip()

        if (
            re.search(r'\btotal\b', lower)
            and 'sub' not in lower
            and 'qty' not in lower
            and 'quantity' not in lower
            and 'tax' not in lower
            and 'cgst' not in lower
            and 'sgst' not in lower
        ):

            nums = re.findall(
                r'[\d,]+(?:\.\d{1,2})?',
                line
            )

            for n in reversed(nums):

                try:

                    value = float(
                        n.replace(",", "")
                    )

                    if 1 <= value <= 100000:
                        return value

                except:
                    pass

    # --------------------------------
    # PRIORITY 2:
    # last reasonable amount
    # near bottom of receipt
    # --------------------------------

    bottom_lines = lines[len(lines)//2:]

    bottom_amounts = []

    for line in bottom_lines:

        nums = re.findall(
            r'[\d,]+(?:\.\d{1,2})?',
            line
        )

        for n in nums:

            try:

                value = float(
                    n.replace(",", "")
                )

                # ignore GST IDs etc.
                if 20 <= value <= 50000:

                    bottom_amounts.append(value)

            except:
                pass

    if bottom_amounts:
        return bottom_amounts[-1]

    # --------------------------------
    # PRIORITY 3:
    # subtotal fallback
    # --------------------------------

    for line in lines:

        if (
            'sub total' in line.lower()
            or 'subtotal' in line.lower()
        ):

            nums = re.findall(
                r'[\d,]+(?:\.\d{1,2})?',
                line
            )

            for n in reversed(nums):

                try:

                    value = float(
                        n.replace(",", "")
                    )

                    if 1 <= value <= 100000:
                        return value

                except:
                    pass

    # --------------------------------
    # PRIORITY 4:
    # currency-prefixed amounts
    # --------------------------------

    amounts = re.findall(
        r'(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)',
        text,
        re.IGNORECASE
    )

    if amounts:

        return max(
            float(a.replace(",", ""))
            for a in amounts
        )

    return None

# -----------------------------
# DATE EXTRACTION
# -----------------------------

def parse_date(text: str):
    patterns = [
        # "20-May-18" or "20-May-2018"  ← NEW
        (r'(\d{1,2})[\/\-]([A-Za-z]{3,9})[\/\-](\d{2,4})', 'dMonY'),
        # DD/MM/YYYY or DD-MM-YYYY
        (r'(\d{2})[\/\-](\d{2})[\/\-](\d{4})', 'dmy'),
        # DD/MM/YY
        (r'(\d{2})[\/\-](\d{2})[\/\-](\d{2})', 'dmy_short'),
        # YYYY-MM-DD
        (r'(\d{4})[\/\-](\d{2})[\/\-](\d{2})', 'ymd'),
    ]

    for pat, fmt in patterns:
        match = re.search(pat, text)
        if match:
            try:
                g = match.groups()
                if fmt == 'dMonY':
                    year = int(g[2])
                    if year < 100:
                        year += 2000
                    # handles both 3-letter (May) and full (January)
                    month_fmt = "%b" if len(g[1]) == 3 else "%B"
                    return datetime.strptime(
                        f"{int(g[0]):02d} {g[1][:3].capitalize()} {year}",
                        f"%d %b %Y"
                    ).date()
                elif fmt == 'ymd':
                    return date(int(g[0]), int(g[1]), int(g[2]))
                else:
                    year = int(g[2])
                    if year < 100:
                        year += 2000
                    return date(year, int(g[1]), int(g[0]))
            except:
                pass

    return date.today()

# -----------------------------
# CATEGORY DETECTION
# -----------------------------

def detect_category(text: str):

    text = text.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():

        for kw in keywords:

            if kw in text:
                return category

    return "Other"

# -----------------------------
# DESCRIPTION
# -----------------------------

def extract_description(text: str):

    for line in text.splitlines():

        line = line.strip()

        if len(line) > 3:
            return line[:100]

    return "Scanned Receipt"

# -----------------------------
# OCR ROUTE
# -----------------------------

@router.post("/scan")
async def scan_receipt(

    file: UploadFile = File(...),

    db: Session = Depends(get_db),

    current_user = Depends(get_current_user),
):

    if not file.content_type.startswith("image/"):

        raise HTTPException(
            status_code=400,
            detail="Upload an image file"
        )

    image_bytes = await file.read()

    try:

        raw_text = extract_text(image_bytes)

        print("\n------ OCR TEXT ------")
        print(raw_text)
        print("----------------------")

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"OCR failed: {e}"
        )

    amount = parse_amount(raw_text)

    if amount is None:

        raise HTTPException(
            status_code=422,
            detail="Could not detect amount"
        )

    expense_date = parse_date(raw_text)

    category = detect_category(raw_text)

    description = extract_description(raw_text)

    print("AMOUNT:", amount)
    print("DATE:", expense_date)
    print("CATEGORY:", category)

    # SAVE TO DB

    expense = Expense(

        user_id=current_user.id,

        amount=amount,

        currency="INR",

        category=category,

        description=description,

        date=expense_date,
    )

    db.add(expense)

    db.commit()

    db.refresh(expense)

    return {

        "message": "Expense added successfully",

        "expense_id": expense.id,

        "amount": amount,

        "category": category,

        "description": description,

        "date": expense_date.isoformat(),
    }