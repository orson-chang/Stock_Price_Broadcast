# Stock_Price_Broadcast
盤前傳送美股持股報價

持股標的存在spider_web.ods

打開ODS檔案，找出持股標的

每個一個小時，推送以下資訊

股票代碼/股價/行權價_若有/下次買點/下次賣點


```
Project/
├── main.py
├── config.py
│
├── data/
│   └── my_stock.ods
│
├── broker/
│   └── ib/
│       ├── __init__.py
│       ├── gateway.py          # 連線、disconnect、共用 client
│       ├── orders.py           # ib_limit_order()
│       ├── option_contracts.py # ib_lookup_delta_in_contracts() & ib_fetch_premium_ask_bid()
││      └── stock_data.py      # ib_fetch_stock_price()
│
├── strategy/
│   ├── spiderweb.py
│   ├── spiderweb_plan.py
│   ├── bear_spread.py
│   ├── bull_spread.py
│   ├── covered_call.py
│   └── cash_secured_put.py
│
├── notification/
│   ├── line_push.py
│   └── line_receive.py
│
└── logs/
    └── trade_log.txt
```
