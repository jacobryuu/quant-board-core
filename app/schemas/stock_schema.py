from pydantic import BaseModel
from typing import List, Optional
from datetime import date


# --- Request Schemas ---
class TickerList(BaseModel):
    tickers: List[str]


# --- Base Schemas ---
# These are used as a base for other schemas and are not meant to be used directly
class StockBase(BaseModel):
    code: str
    name: str
    industry: Optional[str] = None
    sector: Optional[str] = None
    country: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    market_cap: Optional[int] = None
    website: Optional[str] = None


class DailyStockPriceBase(BaseModel):
    date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adj_close: Optional[float] = None
    volume: Optional[int] = None
    dividends: Optional[float] = 0.0
    stock_splits: Optional[float] = 0.0


class FinancialStatementBase(BaseModel):
    period_type: str
    period_end_date: date
    total_revenue: Optional[int] = None
    cost_of_revenue: Optional[int] = None
    gross_profit: Optional[int] = None
    operating_income: Optional[int] = None
    net_income: Optional[int] = None
    total_assets: Optional[int] = None
    total_liabilities: Optional[int] = None
    shareholder_equity: Optional[int] = None
    free_cash_flow: Optional[int] = None


# --- Create Schemas ---
class StockCreate(StockBase):
    pass


class DailyStockPriceCreate(DailyStockPriceBase):
    pass


class FinancialStatementCreate(FinancialStatementBase):
    pass


# --- Read Schemas ---
class DailyStockPrice(DailyStockPriceBase):
    id: int
    stock_id: int

    class Config:
        from_attributes = True


class FinancialStatement(FinancialStatementBase):
    id: int
    stock_id: int

    class Config:
        from_attributes = True


class StockSimple(StockBase):
    """
    銘柄一覧表示用のシンプルなスキーマ
    """

    id: int

    class Config:
        from_attributes = True


class Stock(StockBase):
    id: int
    daily_prices: List[DailyStockPrice] = []
    financial_statements: List[FinancialStatement] = []

    class Config:
        from_attributes = True
