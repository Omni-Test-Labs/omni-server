"""API package initialization for version 3 with GraphQL support."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from omni_server.database import get_db
from omni_server.graphql import schema as graphql_schema

router = APIRouter(prefix="", tags=["api-v3", "graphql"])


# GraphQL endpoint using Strawberry's ASGI handler
@router.post("/graphql")
async def graphql_handler(request: Request):
    """Handle GraphQL HTTP POST requests."""
    from strawberry.asgi import GraphQL as GraphQLASGI
    from strawberry.schema.config import StrawberryConfig

    # GraphQL context function
    async def get_context() -> dict:
        """Get GraphQL context with database session."""
        async for db in get_db():
            return {"db": db}

    # Create GraphQL ASGI app
    graphql_app = GraphQLASGI(
        schema,
        context_getter=get_context,
        debug=True,
    )

    # Forward to GraphQL ASGI
    return await graphql_app.handle(request)


# GraphQL playground route
@router.get("/graphql", response_class=HTMLResponse)
async def graphql_playground():
    """Serve GraphQL Playground UI."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GraphQL Playground</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.26/build/static/css/index.css" />
        <link rel="shortcut icon" href="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.26/build/favicon.png" />
        <script src="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.26/build/static/js/middleware.js"></script>
    </head>
    <body>
        <div id="root"></div>
        <script>
            window.addEventListener('load', function(event) {
                GraphQLPlayground.init(document.getElementById('root'), {
                    endpoint: '/api/v3/graphql',
                    subscriptionEndpoint: '/api/v3/graphql'
                });
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# GraphQL health check for v3
@router.get("/health")
async def graphql_health():
    """Health check for GraphQL API."""
    return {"status": "ok", "graphql": "v1"}


__all__ = ["router"]
