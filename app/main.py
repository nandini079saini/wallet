'''hello'''
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from .database import Base, engine
from .routers import auth_routes, expense_routes, bill_routes, income_routes, ocr_routes
from .reminders import start_scheduler


# Create tables
Base.metadata.create_all(bind=engine)


app = FastAPI(title="Personal Finance API")

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "https://wallet-app-tracker.netlify.app"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)
# Routers
app.include_router(auth_routes.router)
app.include_router(expense_routes.router)
app.include_router(bill_routes.router)
app.include_router(income_routes.router)
app.include_router(ocr_routes.router)


scheduler = None

@app.on_event("startup")
def on_startup():
    global scheduler
    scheduler = start_scheduler()

@app.get("/")
def home():
    return {"message": "Backend running!"}

