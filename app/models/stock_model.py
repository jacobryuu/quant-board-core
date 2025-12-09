from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    ForeignKey,
    DateTime,
    func,
    BigInteger,
)
from sqlalchemy.orm import relationship
from app.database.connection import Base  # Import Base from connection.py


class Stock(Base):
    """
    株の基本情報モデル
    yfinanceのTicker.infoから取得できる企業のメタ情報を保存
    """

    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    industry = Column(String)  # 業界
    sector = Column(String)  # 業種
    country = Column(String)  # 国
    exchange = Column(String)  # 取引所
    currency = Column(String)  # 通貨
    market_cap = Column(BigInteger)  # 時価総額
    website = Column(String)  # 企業のウェブサイトURL
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    daily_prices = relationship("DailyStockPrice", back_populates="stock")
    financial_statements = relationship(
        "FinancialStatement", back_populates="stock"
    )  # 復活


class DailyStockPrice(Base):
    """
    日々の株価情報モデル
    yfinanceのTicker.history()から取得できる日々の価格情報を保存
    """

    __tablename__ = "daily_stock_prices"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    adj_close = Column(Float)  # 調整済み終値
    volume = Column(BigInteger)  # BigIntegerに変更
    dividends = Column(Float, default=0.0)  # 配当
    stock_splits = Column(Float, default=0.0)  # 株式分割
    created_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="daily_prices")


class FinancialStatement(Base):
    """
    財務情報モデル
    yfinanceのTicker.financialsやTicker.quarterly_financialsから取得できる財務諸表を保存
    """

    __tablename__ = "financial_statements"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    period_type = Column(String, nullable=False)  # 'annual' or 'quarterly'
    period_end_date = Column(Date, nullable=False)  # 決算日
    total_revenue = Column(BigInteger)  # 総収益
    cost_of_revenue = Column(BigInteger)  # 売上原価
    gross_profit = Column(BigInteger)  # 売上総利益
    operating_income = Column(BigInteger)  # 営業利益
    net_income = Column(BigInteger)  # 純利益
    total_assets = Column(BigInteger)  # 総資産
    total_liabilities = Column(BigInteger)  # 総負債
    shareholder_equity = Column(BigInteger)  # 株主資本
    free_cash_flow = Column(BigInteger)  # フリーキャッシュフロー
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    stock = relationship("Stock", back_populates="financial_statements")
