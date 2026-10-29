"""Isolated paper-trading worker placeholder. There is no live broker adapter."""
import asyncio

async def main():
    print("trading-worker ready: paper mode only; live execution is unsupported")
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
