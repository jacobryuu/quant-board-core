import yfinance as yf
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import math

from app.models import stock_model
from app.schemas import stock_schema


def _clean_financial_value(value):
    """
    yfinanceから来る可能性のあるNaNやinfをNoneに変換する
    """
    if value is None or not math.isfinite(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class StockService:
    def __init__(self, db: Session):
        self.db = db

    def get_stock_by_code(self, code: str) -> Optional[stock_model.Stock]:
        """
        銘柄コードで株式情報を取得
        """
        return (
            self.db.query(stock_model.Stock)
            .filter(stock_model.Stock.code == code)
            .first()
        )

    def create_stock(self, stock: stock_schema.StockCreate) -> stock_model.Stock:
        """
        新しい株式情報を作成
        """
        db_stock = stock_model.Stock(**stock.model_dump())
        self.db.add(db_stock)
        self.db.commit()
        self.db.refresh(db_stock)
        return db_stock

    def add_daily_prices(
        self, stock_id: int, prices: List[stock_schema.DailyStockPriceCreate]
    ):
        """
        日次株価データを一括で追加
        """
        db_prices = [
            stock_model.DailyStockPrice(stock_id=stock_id, **p.model_dump())
            for p in prices
        ]
        self.db.bulk_save_objects(db_prices)
        self.db.commit()

    def get_daily_prices(
        self,
        stock_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[stock_model.DailyStockPrice]:
        """
        指定された期間の日次株価データを取得
        """
        query = self.db.query(stock_model.DailyStockPrice).filter(
            stock_model.DailyStockPrice.stock_id == stock_id
        )
        if start_date:
            query = query.filter(stock_model.DailyStockPrice.date >= start_date)
        if end_date:
            query = query.filter(stock_model.DailyStockPrice.date <= end_date)
        return query.order_by(stock_model.DailyStockPrice.date).all()

    def get_all_stocks(
        self, skip: int = 0, limit: int = 100
    ) -> List[stock_model.Stock]:
        """
        株式情報をページネーションで取得
        """
        return self.db.query(stock_model.Stock).offset(skip).limit(limit).all()

    def create_financial_statement(
        self, stock_id: int, statement: stock_schema.FinancialStatementCreate
    ) -> stock_model.FinancialStatement:
        """
        財務情報を作成
        """
        db_statement = stock_model.FinancialStatement(
            stock_id=stock_id, **statement.model_dump()
        )
        self.db.add(db_statement)
        self.db.commit()
        self.db.refresh(db_statement)
        return db_statement

    def get_financial_statements(
        self,
        stock_id: int,
        period_type: Optional[str] = None,
        period_end_date: Optional[date] = None,
    ) -> List[stock_model.FinancialStatement]:
        """
        指定された条件で財務情報を取得
        """
        query = self.db.query(stock_model.FinancialStatement).filter(
            stock_model.FinancialStatement.stock_id == stock_id
        )
        if period_type:
            query = query.filter(
                stock_model.FinancialStatement.period_type == period_type
            )
        if period_end_date:
            query = query.filter(
                stock_model.FinancialStatement.period_end_date == period_end_date
            )
        return query.order_by(
            stock_model.FinancialStatement.period_end_date.desc()
        ).all()

    def _save_financials_from_df(self, stock_id: int, financials_df, period_type: str):
        """
        yfinanceから取得した財務データ(DataFrame)をDBに保存するヘルパー関数
        """
        if financials_df.empty:
            return

        financials_df_transposed = financials_df.T
        for period_end_date, row in financials_df_transposed.iterrows():
            # 既に同じデータが存在するか確認
            existing_statement = self.get_financial_statements(
                stock_id=stock_id,
                period_type=period_type,
                period_end_date=period_end_date.date(),
            )
            if existing_statement:
                continue  # 存在する場合はスキップ

            # yfinanceの列名とモデルの属性名をマッピングし、値をクリーンにする
            statement_data = stock_schema.FinancialStatementCreate(
                period_type=period_type,
                period_end_date=period_end_date.date(),
                total_revenue=_clean_financial_value(row.get("Total Revenue")),
                cost_of_revenue=_clean_financial_value(row.get("Cost Of Revenue")),
                gross_profit=_clean_financial_value(row.get("Gross Profit")),
                operating_income=_clean_financial_value(row.get("Operating Income")),
                net_income=_clean_financial_value(row.get("Net Income")),
                total_assets=_clean_financial_value(row.get("Total Assets")),
                total_liabilities=_clean_financial_value(row.get("Total Liabilities")),
                shareholder_equity=_clean_financial_value(
                    row.get("Stockholders Equity")
                ),
                free_cash_flow=_clean_financial_value(row.get("Free Cash Flow")),
            )
            self.create_financial_statement(stock_id, statement_data)
        print(f"Saved {period_type} financial statements.")

    def fetch_and_save_yfinance_data(
        self, ticker_symbol: str
    ) -> Optional[stock_model.Stock]:
        """
        yfinanceから株価・財務データを取得し、DBに保存する
        """
        print(
            f"DEBUG: fetch_and_save_yfinance_data called for ticker: {ticker_symbol}"
        )  # DEBUG LOG
        ticker = yf.Ticker(ticker_symbol)

        # infoの取得に失敗した場合（例: 銘柄が存在しない）、早期にリターン
        if not ticker.info or "symbol" not in ticker.info:
            print(
                f"Could not fetch info for ticker: {ticker_symbol}. It may not exist."
            )
            return None

        info = ticker.info
        stock = self.get_stock_by_code(code=ticker_symbol)

        stock_data_dict = {
            "code": ticker_symbol,
            "name": info.get("longName", info.get("shortName", ticker_symbol)),
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "country": info.get("country"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "market_cap": _clean_financial_value(info.get("marketCap")),
            "website": info.get("website"),
        }

        if stock:
            for key, value in stock_data_dict.items():
                setattr(stock, key, value)
            self.db.commit()
            self.db.refresh(stock)
        else:
            stock_data = stock_schema.StockCreate(**stock_data_dict)
            stock = self.create_stock(stock_data)

        if not stock:
            return None

        hist = ticker.history(period="max", auto_adjust=False)
        if not hist.empty:
            latest_price = (
                self.db.query(stock_model.DailyStockPrice)
                .filter(stock_model.DailyStockPrice.stock_id == stock.id)
                .order_by(stock_model.DailyStockPrice.date.desc())
                .first()
            )

            prices_to_add = []
            for index, row in hist.iterrows():
                if latest_price and index.date() <= latest_price.date:
                    continue

                prices_to_add.append(
                    stock_schema.DailyStockPriceCreate(
                        date=index.date(),
                        open=row.get("Open"),
                        high=row.get("High"),
                        low=row.get("Low"),
                        close=row.get("Close"),
                        adj_close=row.get("Adj Close"),
                        volume=_clean_financial_value(row.get("Volume")),
                        dividends=row.get("Dividends", 0.0),
                        stock_splits=row.get("Stock Splits", 0.0),
                    )
                )

            if prices_to_add:
                self.add_daily_prices(stock.id, prices_to_add)
            print(f"Saved {len(prices_to_add)} new daily price records.")

        self._save_financials_from_df(stock.id, ticker.financials, "annual")
        self._save_financials_from_df(
            stock.id, ticker.quarterly_financials, "quarterly"
        )

        return stock


def run_bulk_fetch_job(ticker_symbols: List[str]):
    """
    バックグラウンドで実行される一括データ取得・保存ジョブ
    """
    from app.database.connection import SessionLocal

    db = SessionLocal()
    service = StockService(db)
    print(
        f"DEBUG: run_bulk_fetch_job received ticker_symbols: {ticker_symbols}"
    )  # DEBUG LOG
    print(f"Starting bulk fetch job for {len(ticker_symbols)} tickers.")

    success_count = 0
    failure_count = 0

    try:
        for ticker in ticker_symbols:
            try:
                print(f"Fetching data for {ticker}...")
                stock = service.fetch_and_save_yfinance_data(ticker)
                if stock:
                    print(f"Successfully saved data for {ticker}.")
                    success_count += 1
                else:
                    print(f"Failed to fetch data for {ticker}.")
                    failure_count += 1
            except Exception as e:
                print(f"An error occurred while fetching data for {ticker}: {e}")
                failure_count += 1
    finally:
        db.close()
        print("Bulk fetch job finished.")
        print(f"Summary: Success = {success_count}, Failure = {failure_count}")
