import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import patch, MagicMock

from app.main import app
from app.database.connection import Base
from app.routers.stocks import get_db  # get_db is defined in the router
from app.models import stock_model


import pandas as pd
from datetime import date

# --- Test Database Setup ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override the get_db dependency for all tests
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Use a single client for all tests
client = TestClient(app)

# --- Pytest Fixtures ---


@pytest.fixture(scope="function")
def db_session():
    """
    Fixture to handle test database creation and cleanup for each test function.
    """
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_yfinance():
    """
    Fixture to mock yfinance.Ticker and its methods.
    """
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()

        # Mock .info
        mock_ticker_instance.info = {
            "longName": "Test Inc",
            "industry": "Technology",
            "sector": "Software",
            "country": "USA",
            "exchange": "NASDAQ",
            "currency": "USD",
            "marketCap": 1_000_000_000,
            "website": "https://example.com",
            "symbol": "TEST",
        }

        # Mock .history
        hist_data = {
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [101.0],
            "Adj Close": [101.0],
            "Volume": [100000],
            "Dividends": [0.0],
            "Stock Splits": [0.0],
        }
        hist_index = pd.to_datetime(["2023-01-01"])
        mock_ticker_instance.history.return_value = pd.DataFrame(
            hist_data, index=hist_index
        )

        # Mock .financials (annual)
        fin_data = {
            "Total Revenue": [10000],
            "Net Income": [2000],
            "Total Assets": [30000],
            "Stockholders Equity": [15000],
            "Total Liabilities": [15000],
            "Cost Of Revenue": [4000],
            "Gross Profit": [6000],
            "Operating Income": [3000],
            "Free Cash Flow": [1000],
        }
        fin_index = pd.to_datetime(["2023-12-31"])
        mock_ticker_instance.financials = pd.DataFrame(
            fin_data, index=fin_index
        ).T  # Transpose to match yfinance format

        # Mock .quarterly_financials
        q_fin_data = {"Total Revenue": [2500], "Net Income": [500]}
        q_fin_index = pd.to_datetime(["2024-03-31"])
        mock_ticker_instance.quarterly_financials = pd.DataFrame(
            q_fin_data, index=q_fin_index
        ).T

        mock_ticker_class.return_value = mock_ticker_instance
        yield mock_ticker_class


# --- Test Cases ---


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Quant Board Core API"}


def test_create_and_get_stock_detail(db_session: Session):
    # Create
    response = client.post(
        "/stocks/",
        json={"code": "MANUAL", "name": "Manual Corp", "industry": "Testing"},
    )
    assert response.status_code == 201
    created_data = response.json()
    assert created_data["code"] == "MANUAL"
    assert created_data["id"] is not None

    # Get Detail
    response = client.get(f"/stocks/{created_data['code']}")
    assert response.status_code == 200
    retrieved_data = response.json()
    assert retrieved_data["name"] == "Manual Corp"
    assert retrieved_data["daily_prices"] == []  # Should be empty


def test_create_stock_duplicate(db_session: Session):
    client.post("/stocks/", json={"code": "DUPE", "name": "Dupe Corp"})
    response = client.post("/stocks/", json={"code": "DUPE", "name": "Dupe Corp"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_stock_not_found(db_session: Session):
    response = client.get("/stocks/NONEXISTENT")
    assert response.status_code == 404


def test_get_all_stocks_paginated(db_session: Session):
    # Create 3 stocks
    client.post("/stocks/", json={"code": "S1", "name": "Stock 1"})
    client.post("/stocks/", json={"code": "S2", "name": "Stock 2"})
    client.post("/stocks/", json={"code": "S3", "name": "Stock 3"})

    # Get all
    response = client.get("/stocks/")
    assert response.status_code == 200
    assert len(response.json()) == 3

    # Test limit
    response = client.get("/stocks/?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["code"] == "S1"

    # Test skip and limit
    response = client.get("/stocks/?skip=1&limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["code"] == "S2"


def test_fetch_yfinance_data_new_stock(db_session: Session, mock_yfinance):
    ticker = "TEST"
    response = client.post(f"/stocks/yfinance/{ticker}")
    assert response.status_code == 200

    # Verify data in DB
    stock = db_session.query(stock_model.Stock).filter_by(code=ticker).one()
    assert stock.name == "Test Inc"
    assert stock.market_cap == 1_000_000_000

    prices = (
        db_session.query(stock_model.DailyStockPrice).filter_by(stock_id=stock.id).all()
    )
    assert len(prices) == 1
    assert prices[0].close == 101.0
    assert prices[0].date == date(2023, 1, 1)

    financials = (
        db_session.query(stock_model.FinancialStatement)
        .filter_by(stock_id=stock.id)
        .all()
    )
    assert len(financials) == 2  # 1 annual, 1 quarterly
    annual = next(f for f in financials if f.period_type == "annual")
    assert annual.total_revenue == 10000
    assert annual.net_income == 2000


def test_trigger_bulk_fetch():
    with patch("app.routers.stocks.run_bulk_fetch_job") as mock_bulk_job:
        response = client.post("/stocks/yfinance/bulk", json={"tickers": ["T1", "T2"]})
        assert response.status_code == 202
        assert "job started" in response.json()["message"]

        # Check that the background task was added with the correct arguments
        mock_bulk_job.assert_called_once_with(["T1", "T2"])


def test_create_and_get_financial_statement(db_session: Session):
    # First create a stock to associate with
    stock_res = client.post("/stocks/", json={"code": "FIN", "name": "Financial Corp"})
    stock_code = stock_res.json()["code"]

    # Create a financial statement for this stock
    fs_payload = {
        "period_type": "annual",
        "period_end_date": "2023-12-31",
        "total_revenue": 500,
        "net_income": 50,
    }
    response_create = client.post(f"/stocks/{stock_code}/financials/", json=fs_payload)
    assert response_create.status_code == 201
    assert response_create.json()["total_revenue"] == 500

    # Get the financial statement back
    response_get = client.get(f"/stocks/{stock_code}/financials/")
    assert response_get.status_code == 200
    assert len(response_get.json()) == 1
    assert response_get.json()[0]["net_income"] == 50
