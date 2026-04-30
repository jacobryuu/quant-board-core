from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database.connection import create_db_tables, DATABASE_URL
from app.routers import stocks


# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    アプリケーションの起動時と終了時に処理を行う
    """
    print(f"Connecting to database: {DATABASE_URL}")
    create_db_tables()
    print("Database tables checked/created.")
    yield
    print("Application shutdown.")


# --- FastAPI App Initialization ---
app = FastAPI(
    title="Quant Board Core API",
    description="API for collecting and managing stock market data.",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Include Routers ---
app.include_router(stocks.router)


# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def root():
    """
    Welcome endpoint.
    """
    return {"message": "Welcome to Quant Board Core API"}
