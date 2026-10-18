"""Mongo connection lifecycle and FastAPI database dependency."""
from os import environ
from fastapi import Request
from dotenv import load_dotenv
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

load_dotenv()


def open_database() -> tuple[AsyncMongoClient, AsyncDatabase]:
    uri = environ.get("MONGODB_URI", "").strip()
    database_name = environ.get("MONGODB_DATABASE", "").strip()
    if not uri or not database_name:
        raise RuntimeError("Set MONGODB_URI and MONGODB_DATABASE in the API environment")
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise RuntimeError("MONGODB_URI must use mongodb:// or mongodb+srv://")
    client = AsyncMongoClient(uri, appname="goldsetu-api", serverSelectionTimeoutMS=8000)
    return client, client[database_name]


async def get_database(request: Request) -> AsyncDatabase:
    return request.app.state.database
