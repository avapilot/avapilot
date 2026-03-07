"""FastAPI marketplace for discovering and publishing MCP servers."""

import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .models import ListingCreate, Listing
from . import registry


def create_app() -> FastAPI:
    app = FastAPI(title="AvaPilot Marketplace", version="0.1.0")
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    @app.get("/")
    async def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    @app.get("/api/listings")
    async def get_listings(chain: str = None, search: str = None):
        listings = registry.list_listings(chain=chain, search=search)
        return [l.model_dump() for l in listings]

    @app.post("/api/listings")
    async def create_listing(data: ListingCreate):
        listing = registry.create_listing(data)
        return listing.model_dump()

    @app.get("/api/listings/{listing_id}")
    async def get_listing(listing_id: str):
        listing = registry.get_listing(listing_id)
        if not listing:
            raise HTTPException(404, "Listing not found")
        return listing.model_dump()

    @app.post("/api/listings/{listing_id}/upvote")
    async def upvote(listing_id: str):
        if registry.upvote_listing(listing_id):
            return {"ok": True}
        raise HTTPException(404, "Listing not found")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    return app
