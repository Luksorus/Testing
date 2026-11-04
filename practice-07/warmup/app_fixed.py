"""Monotonic IDs fix the overwrite defect for a single-process demo."""
from itertools import count

from fastapi import FastAPI, HTTPException, Response

from .app_v0 import ItemIn

app = FastAPI()
ITEMS = {}
NEXT_ID = count(1)


@app.post("/items", status_code=201)
def create_item(item: ItemIn):
    item_id = next(NEXT_ID)
    ITEMS[item_id] = item.model_dump()
    return {"id": item_id, **ITEMS[item_id]}


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="Not found")
    del ITEMS[item_id]
    return Response(status_code=204)
