import os
from io import StringIO
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
import csv
import requests

from database import db, create_document, get_documents
from schemas import Product as ProductSchema, Order as OrderSchema, Contact as ContactSchema, Gallery as GallerySchema, Post as PostSchema

class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")

class ProductOut(BaseModel):
    id: ObjectIdStr
    name: str
    category: str
    price: float
    availability: str
    sku: Optional[str] = None
    care: Optional[str] = None
    image: Optional[str] = None

    @classmethod
    def from_mongo(cls, doc: dict):
        return cls(
            id=str(doc.get("_id")),
            name=doc.get("name"),
            category=doc.get("category"),
            price=doc.get("price"),
            availability=doc.get("availability"),
            sku=doc.get("sku"),
            care=doc.get("care"),
            image=str(doc.get("image")) if doc.get("image") else None,
        )

app = FastAPI(title="Mimoza API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Rasadnik i Cvjećarna Mimoza API"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            collections = db.list_collection_names()
            response["collections"] = collections
            response["connection_status"] = "Connected"
            response["database"] = "✅ Connected & Working"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:100]}"
    return response

# Utility
COLL_PRODUCTS = "product"
COLL_ORDERS = "order"
COLL_CONTACT = "contact"
COLL_GALLERY = "gallery"
COLL_POSTS = "post"

# Products
@app.get("/api/products", response_model=List[ProductOut])
def list_products(category: Optional[str] = None, availability: Optional[str] = None, q: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    query = {}
    if category:
        query["category"] = category
    if availability:
        query["availability"] = availability
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    docs = db[COLL_PRODUCTS].find(query).sort("name", 1)
    return [ProductOut.from_mongo(d) for d in docs]

@app.post("/api/products", response_model=str)
def create_product(product: ProductSchema):
    return create_document(COLL_PRODUCTS, product)

@app.put("/api/products/{product_id}", response_model=ProductOut)
def update_product(product_id: str, product: ProductSchema):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    result = db[COLL_PRODUCTS].find_one_and_update(
        {"_id": ObjectId(product_id)},
        {"$set": product.model_dump()},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return ProductOut.from_mongo(result)

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    res = db[COLL_PRODUCTS].delete_one({"_id": ObjectId(product_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}

# CSV import/export
@app.post("/api/products/import-csv")
def import_products_csv(file: UploadFile = File(...)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    inserted = 0
    for row in reader:
        try:
            doc = ProductSchema(
                name=row.get("name") or row.get("naziv"),
                category=(row.get("category") or row.get("kategorija")),
                price=float(row.get("price") or row.get("cijena") or 0),
                availability=(row.get("availability") or row.get("dostupnost") or "na stanju"),
                sku=row.get("sku"),
                care=row.get("care") or row.get("njega"),
                image=row.get("image") or row.get("slika"),
            )
            db[COLL_PRODUCTS].insert_one(doc.model_dump())
            inserted += 1
        except Exception:
            continue
    return {"inserted": inserted}

@app.get("/api/products/export-csv")
def export_products_csv():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = list(db[COLL_PRODUCTS].find())
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "category", "price", "availability", "sku", "care", "image"])
    for d in docs:
        writer.writerow([
            d.get("name", ""),
            d.get("category", ""),
            d.get("price", ""),
            d.get("availability", ""),
            d.get("sku", ""),
            (d.get("care", "") or "").replace("\n", " "),
            d.get("image", ""),
        ])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=products.csv"
    })

# Orders
@app.post("/api/orders")
def create_order(order: OrderSchema):
    oid = create_document(COLL_ORDERS, order)
    webhook_url = os.getenv("WEBHOOK_URL")
    try:
        if webhook_url:
            requests.post(webhook_url, json={"type": "order", "id": oid, **order.model_dump()})
    except Exception:
        pass
    return {"id": oid}

# Contact
@app.post("/api/contact")
def create_contact(msg: ContactSchema):
    cid = create_document(COLL_CONTACT, msg)
    webhook_url = os.getenv("WEBHOOK_URL")
    try:
        if webhook_url:
            requests.post(webhook_url, json={"type": "contact", "id": cid, **msg.model_dump()})
    except Exception:
        pass
    return {"id": cid}

# Gallery and posts (read-only collections for site content)
@app.get("/api/gallery", response_model=List[dict])
def list_gallery():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = get_documents(COLL_GALLERY)
    # Ensure id is string and alt exists
    for d in docs:
        d["id"] = str(d.pop("_id")) if d.get("_id") else None
        d.setdefault("alt", d.get("title", "Fotografija"))
    return docs

@app.get("/api/posts", response_model=List[dict])
def list_posts():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = db[COLL_POSTS].find({"published": True}).sort("_id", -1)
    out = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out

# Schemas endpoint for admin tooling
@app.get("/schema")
def get_schema_info():
    return {
        "collections": [
            {
                "name": "product",
                "fields": list(ProductSchema.model_fields.keys()),
            },
            {
                "name": "order",
                "fields": list(OrderSchema.model_fields.keys()),
            },
            {
                "name": "contact",
                "fields": list(ContactSchema.model_fields.keys()),
            },
            {
                "name": "gallery",
                "fields": list(GallerySchema.model_fields.keys()),
            },
            {
                "name": "post",
                "fields": list(PostSchema.model_fields.keys()),
            },
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
