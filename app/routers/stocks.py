from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database.connection import SessionLocal
from app.schemas import stock_schema
from app.services.stock_service import (
    StockService,
    run_bulk_fetch_job,
)  # get_jpx_tickers は削除済み

router = APIRouter(
    prefix="/stocks",
    tags=["stocks"],
)


# --- Dependencies ---
def get_db():
    """
    データベースセッションを提供するDependency
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- API Endpoints ---


@router.get(
    "/",
    response_model=List[stock_schema.StockSimple],
    summary="保存されている銘柄一覧をページネーションで取得",
)
async def get_all_stocks(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    データベースに保存されている株式の基本情報を一覧で取得します。
    - `skip`: スキップする件数
    - `limit`: 取得する最大件数
    """
    service = StockService(db)
    return service.get_all_stocks(skip=skip, limit=limit)


@router.post(
    "/yfinance/bulk",
    status_code=status.HTTP_202_ACCEPTED,
    summary="yfinanceから複数銘柄の株価・財務データを一括で取得・保存（バックグラウンド処理）",
)
async def fetch_and_save_bulk_from_yfinance(
    ticker_list: stock_schema.TickerList,
    background_tasks: BackgroundTasks,
):
    """
    yfinanceから指定された複数銘柄の株価・財務データをバックグラウンドで取得し、データベースに保存します。
    - APIはリクエストを受け付けるとすぐにレスポンスを返します。
    - 実際のデータ取得・保存処理はバックグラウンドで実行されます。
    - 処理の進捗や結果は、サーバーのログを確認してください。
    """
    background_tasks.add_task(run_bulk_fetch_job, ticker_list.tickers)
    return {
        "message": (
            "Bulk fetch job started in the background for "
            f"{len(ticker_list.tickers)} tickers."
        ),
    }


@router.post(
    "/yfinance/{ticker_symbol}",
    response_model=stock_schema.Stock,
    summary="yfinanceから株価・財務データを取得・保存",
)
async def fetch_and_save_from_yfinance(
    ticker_symbol: str, db: Session = Depends(get_db)
):
    """
    yfinanceから指定された銘柄コードの株価・財務データを取得し、データベースに保存します。
    - 銘柄情報が存在しない場合は、新規に作成または更新します。
    - 株価データは、DBに保存されている最新の日付以降のデータのみを追加します。
    - 財務データも自動的に取得・保存されます。
    """
    service = StockService(db)
    stock = service.fetch_and_save_yfinance_data(ticker_symbol)
    if not stock:
        raise HTTPException(
            status_code=404, detail=f"Could not fetch data for ticker {ticker_symbol}"
        )

    db.refresh(stock)
    stock.daily_prices = service.get_daily_prices(stock_id=stock.id)
    stock.financial_statements = service.get_financial_statements(stock_id=stock.id)
    return stock


@router.get(
    "/{code}",
    response_model=stock_schema.Stock,
    summary="銘柄情報を取得",
)
async def get_stock(code: str, db: Session = Depends(get_db)):
    """
    指定された銘柄コードの基本情報と、関連する日次株価、財務情報を取得します。
    """
    service = StockService(db)
    stock = service.get_stock_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with code {code} not found")

    # Eagerly load related data for response
    stock.daily_prices
    stock.financial_statements
    return stock


@router.post(
    "/",
    response_model=stock_schema.Stock,
    status_code=201,
    summary="新しい銘柄を手動で登録",
)
async def create_stock(stock: stock_schema.StockCreate, db: Session = Depends(get_db)):
    """
    新しい銘柄の基本情報をデータベースに登録します。
    """
    service = StockService(db)
    existing_stock = service.get_stock_by_code(stock.code)
    if existing_stock:
        raise HTTPException(
            status_code=400, detail=f"Stock with code {stock.code} already exists"
        )
    return service.create_stock(stock)


@router.get(
    "/{code}/prices",
    response_model=List[stock_schema.DailyStockPrice],
    summary="日次株価データを取得",
)
async def get_prices_for_stock(
    code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    指定された銘柄の特定期間の日次株価データを取得します。
    """
    service = StockService(db)
    stock = service.get_stock_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with code {code} not found")
    return service.get_daily_prices(stock.id, start_date, end_date)


@router.post(
    "/{code}/financials/",
    response_model=stock_schema.FinancialStatement,
    status_code=201,
    summary="財務情報を追加",
)
async def create_financial_statement_for_stock(
    code: str,
    statement: stock_schema.FinancialStatementCreate,
    db: Session = Depends(get_db),
):
    """
    指定された銘柄に新しい財務情報を追加します。
    """
    service = StockService(db)
    stock = service.get_stock_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with code {code} not found")
    return service.create_financial_statement(stock.id, statement)


@router.get(
    "/{code}/financials/",
    response_model=List[stock_schema.FinancialStatement],
    summary="財務情報を取得",
)
async def get_financial_statements_for_stock(
    code: str,
    period_type: Optional[str] = None,
    period_end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    指定された銘柄の財務情報を取得します。
    - period_type: 'annual' または 'quarterly' でフィルタリングできます。
    - period_end_date: 特定の決算日でフィルタリングできます。
    """
    service = StockService(db)
    stock = service.get_stock_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with code {code} not found")
    return service.get_financial_statements(stock.id, period_type, period_end_date)
