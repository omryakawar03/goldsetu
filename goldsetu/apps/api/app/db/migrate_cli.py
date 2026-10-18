"""Run the numbered database migrations once per release, never in API workers."""
import asyncio
from app.db.connection import open_database
from app.db.migrations import migrate


async def main() -> None:
    client, database = open_database()
    try:
        await client.admin.command("ping")
        versions = await migrate(database)
        if versions:
            print("Applied schema migrations:", ", ".join(map(str, versions)))
        else:
            print("Database schema is already current.")
    finally:
        await client.close()


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
