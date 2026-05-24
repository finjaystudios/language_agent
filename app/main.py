from app.cli.main import main

__all__ = ["main"]


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
