from typing import Optional, Tuple
from redis.asyncio.client import Redis
from fastapi_cache.backends import Backend


# fastapi_cache.backends.RedisBackend adjusted for master+replica configurations

class RedisReplicaBackend(Backend):
    def __init__(self, master: "Redis[bytes]", replica: "Redis[bytes]"):
        self.master = master
        self.replica = replica

    async def get_with_ttl(self, key: str) -> Tuple[int, Optional[bytes]]:
        async with self.replica.pipeline() as pipe:
            return await pipe.ttl(key).get(key).execute()

    async def get(self, key: str) -> Optional[bytes]:
        return await self.replica.get(key)

    async def set(self, key: str, value: bytes, expire: Optional[int] = None) -> None:
        await self.master.set(key, value, ex=expire)

    async def clear(self, namespace: Optional[str] = None, key: Optional[str] = None) -> int:
        if namespace:
            lua = f"for i, name in ipairs(redis.call('KEYS', '{namespace}:*')) do redis.call('DEL', name); end"
            return await self.master.eval(lua, numkeys=0)  # type: ignore[union-attr,no-any-return]
        elif key:
            return await self.master.delete(key)  # type: ignore[union-attr]
        return 0
