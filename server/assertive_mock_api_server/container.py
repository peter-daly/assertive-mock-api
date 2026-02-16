from clean_ioc import Container, Lifespan
from .core import (
    MockApiServer,
    RequestLog,
    ResponseGenerator,
    ScopeRepository,
    StubRepository,
)
import httpx


async def async_client_factory():
    async with httpx.AsyncClient() as client:
        yield client


def get_container():
    """
    Create a container for dependency injection.
    """
    container = Container()

    container.register(MockApiServer, lifespan=Lifespan.singleton)
    container.register(StubRepository, lifespan=Lifespan.singleton)
    container.register(RequestLog, lifespan=Lifespan.singleton)
    container.register(ScopeRepository, lifespan=Lifespan.singleton)
    container.register(ResponseGenerator, lifespan=Lifespan.singleton)
    container.register(
        httpx.AsyncClient,
        lifespan=Lifespan.singleton,
        factory=async_client_factory,
    )

    return container
