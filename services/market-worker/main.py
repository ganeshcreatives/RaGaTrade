"""Demo market adapter. Replace only with a licensed provider implementation."""
import asyncio
import json
import os
from datetime import datetime, timezone
import redis.asyncio as redis

SYMBOLS = {"RELIANCE": 1452.80, "HDFCBANK": 986.45, "TCS": 3184.70, "ICICIBANK": 1272.30, "INFY": 1548.90, "TMPV": 682.15, "BHARTIARTL": 1942.65, "LT": 3624.50, "SUNPHARMA": 1724.35}

async def main():
    client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    print("market-worker started in DEMO mode; no broker feed connected")
    try:
        while True:
            for symbol, price in SYMBOLS.items():
                payload = {"symbol": symbol, "price": price, "timestamp": datetime.now(timezone.utc).isoformat(), "source": "DEMO_DATA"}
                await client.set(f"quote:DEMO:{symbol}", json.dumps(payload), ex=30)
            await asyncio.sleep(5)
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
