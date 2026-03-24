"""API package initialization for version 2."""

from fastapi import APIRouter

router = APIRouter(prefix="", tags=["api-v2"])

# v2 endpoints will be added as needed
# Currently inherits from v1 structure

__all__ = ["router"]
