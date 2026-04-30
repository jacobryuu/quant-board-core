 -- 株の基本情報を保存するテーブル
 CREATE TABLE IF NOT EXISTS stocks (
     id SERIAL PRIMARY KEY,
     code VARCHAR UNIQUE NOT NULL,
     name VARCHAR NOT NULL,
     industry VARCHAR,
     sector VARCHAR,
     country VARCHAR, -- 追加
     exchange VARCHAR,
     currency VARCHAR,
     market_cap BIGINT, -- 追加 (時価総額)
        website VARCHAR, -- 追加 (企業のウェブサイトURL)
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );

    -- stocksテーブルのcodeカラムにインデックスを作成
    CREATE INDEX IF NOT EXISTS ix_stocks_code ON stocks (code);


    -- 日々の株価情報を保存するテーブル
    CREATE TABLE IF NOT EXISTS daily_stock_prices (
       id SERIAL PRIMARY KEY,
       stock_id INTEGER NOT NULL REFERENCES stocks(id),
    date DATE NOT NULL,
     open DOUBLE PRECISION,
       high DOUBLE PRECISION,
       low DOUBLE PRECISION,
       close DOUBLE PRECISION,
       adj_close DOUBLE PRECISION,
        volume BIGINT,
       dividends DOUBLE PRECISION DEFAULT 0.0,
        stock_splits DOUBLE PRECISION DEFAULT 0.0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );

    -- daily_stock_pricesテーブルのdateとstock_idカラムにインデックスを作成
    CREATE INDEX IF NOT EXISTS ix_daily_stock_prices_date ON daily_stock_prices (date);
    CREATE INDEX IF NOT EXISTS ix_daily_stock_prices_stock_id ON daily_stock_prices (stock_id);


    -- 財務情報を保存するテーブル
    CREATE TABLE IF NOT EXISTS financial_statements (
        id SERIAL PRIMARY KEY,
        stock_id INTEGER NOT NULL REFERENCES stocks(id),
        period_type VARCHAR NOT NULL, -- 'annual' or 'quarterly'
        period_end_date DATE NOT NULL, -- 決算日
        total_revenue BIGINT, -- 総収益
        cost_of_revenue BIGINT, -- 売上原価
        gross_profit BIGINT, -- 売上総利益
        operating_income BIGINT, -- 営業利益
        net_income BIGINT, -- 純利益
        total_assets BIGINT, -- 総資産
        total_liabilities BIGINT, -- 総負債
        shareholder_equity BIGINT, -- 株主資本
        free_cash_flow BIGINT, -- フリーキャッシュフロー
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );

    -- financial_statementsテーブルにインデックスを作成
   CREATE INDEX IF NOT EXISTS ix_financial_statements_stock_id ON financial_statements (stock_id);
   CREATE INDEX IF NOT EXISTS ix_financial_statements_period_end_date ON financial_statements (period_end_date);
   CREATE UNIQUE INDEX IF NOT EXISTS ux_financial_statements_stock_id_period_type_period_end_date ON financial_statements (stock_id, period_type, period_end_date);
