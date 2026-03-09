# Line Stock Quote Bot v1

This project implements a LINE webhook bot for stock quote lookup.

## Features

- Receive `Stock` from LINE and reply with `please provide Stock index`
- Treat the next message as a ticker symbol and reply with `{SYMBOL} stock now is {PRICE}`
- Use Alpha Vantage `GLOBAL_QUOTE` for v1 stock prices
- Keep the architecture ready for future IBKR integration

Line APP接收到字串 " Stock "
 
Line 回應 " please provide Stock index"
 
我回應 "NVDA"
 
Line回應 " NVDA stock now is XXX "  XXX為回傳的股價

Line APP接收到字串 "OP "
 
Line 回應 " please provide stock index/MMMDD/strike/C or P" # where MMM=月份, DD=日期, strike=合約行權價 , C for Call P for Put
 
我回應 "NVDA/Mar13/175/P" #(舉例)
 
Line回應 " Provide 7 contracts of NVDA/Mar13/175/P " 
        " strike 175+3rank premium ask/bid = x7/y7 , delta = z7"   
        " strike 175+2rank premium ask/bid = x6/y6 , delta = z6"
        " strike 175+1rank premium ask/bid = x5/y5 , delta = z5"
        " strike 175+0rank premium ask/bid = x4/y4 , delta = z4"   
        " strike 175-1rank premium ask/bid = x3/y3 , delta = z3"
        " strike 175-2rank premium ask/bid = x2/y2 , delta = z2"
        " strike 175-3rank premium ask/bid = x1/y1 , delta = z1"
        # delta為該合約的選擇權希臘字母 delta
由於ib查詢合約名稱與合約ask/bid/delta的架構尚未完成，先用假資料代替
 
## Project Layout

```text
Project/
├── main.py
├── config.py
├── data/
├── broker/
├── strategy/
├── notification/
├── logs/
└── tests/
```

## Requirements

- Python 3.11+
- A LINE Messaging API channel
- An Alpha Vantage API key
- `ngrok` for local webhook exposure

## Setup

1. Open PowerShell in `Stock_Price_Broadcast/Project`.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in real values.

## Run Locally

```powershell
python main.py
```

The Flask server starts on `http://127.0.0.1:5000` by default.

## Expose the Webhook with ngrok

1. Start the Flask app.
2. In another terminal, run:

   ```powershell
   ngrok http 5000
   ```

3. Copy the HTTPS forwarding URL from ngrok.
4. In LINE Developers Console, set the webhook URL to:

   ```text
   https://<your-ngrok-domain>/callback
   ```

5. Enable webhook usage and verify the endpoint.

## Message Flow

1. Send `Stock`
2. Bot replies `please provide Stock index`
3. Send `NVDA`
4. Bot replies `NVDA stock now is XXX`
5. Send `Option`
6. Bot replies `option query is not implemented yet`

## Tests

```powershell
pytest
```

## Notes

- Alpha Vantage `GLOBAL_QUOTE` is accepted as delayed/EOD for v1.
- The quote provider interface is intentionally provider-neutral so IBKR can be added later.
- Logs are written to `logs/trade_log.txt`.
