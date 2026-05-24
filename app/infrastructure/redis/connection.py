from redis import Redis
from redis.asyncio import Redis as AsyncRedis


def get_redis_connection(url: str) -> Redis:
    return Redis.from_url(url)


def get_async_redis_connection(url: str) -> AsyncRedis:
    return AsyncRedis.from_url(url)


async def close_async_redis_connection(connection: AsyncRedis | None) -> None:
    if connection is not None:
        await connection.aclose()
