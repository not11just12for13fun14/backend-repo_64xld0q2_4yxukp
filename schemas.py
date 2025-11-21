"""
Database Schemas for Rasadnik i Cvjećarna Mimoza

Each Pydantic model represents a MongoDB collection (collection name is the lowercase class name).

Collections:
- product: katalog proizvoda/biljaka
- order: narudžbe buketa i aranžmana
- contact: kontakt poruke
- gallery: galerija slika s kreditima
- post: blog/tips objave
"""
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, HttpUrl, EmailStr
from datetime import date


class Product(BaseModel):
    name: str = Field(..., description="Naziv proizvoda/biljke")
    category: Literal[
        "sobne biljke",
        "trajnica",
        "grmovi",
        "zivica",
        "povrtne sadnice",
        "zacinsko bilje",
        "sezonsko cvijece",
        "posude i aranzmani",
    ] = Field(..., description="Kategorija")
    price: float = Field(..., ge=0, description="Cijena u EUR")
    availability: Literal["na stanju", "sezonski", "rasprodano"] = Field(
        "na stanju", description="Dostupnost"
    )
    sku: Optional[str] = Field(None, description="SKU/šifra")
    care: Optional[str] = Field(None, description="Kratke upute za njegu")
    image: Optional[HttpUrl] = Field(None, description="URL slike (WebP preporučen)")


class Order(BaseModel):
    full_name: str = Field(..., description="Ime i prezime naručitelja")
    phone: str = Field(..., description="Telefon")
    email: Optional[EmailStr] = Field(None, description="Email")
    message: Optional[str] = Field(None, description="Napomena / opis")
    event_date: Optional[date] = Field(None, description="Datum događaja")
    pickup: bool = Field(True, description="Preuzimanje osobno")
    delivery: bool = Field(False, description="Dostava")
    budget_eur: Optional[float] = Field(None, ge=0, description="Okvirni budžet u EUR")
    reference_images: Optional[List[HttpUrl]] = Field(
        default=None, description="URL-ovi referentnih fotografija"
    )
    consent: bool = Field(..., description="Privola za obradu podataka")


class Contact(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    message: str
    consent: bool


class Gallery(BaseModel):
    title: str
    category: Literal["staklenik", "buketi", "krajobraz", "sezonske vitrine"]
    image: HttpUrl
    photographer: Optional[str] = None
    alt: Optional[str] = None


class Post(BaseModel):
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    cover_image: Optional[HttpUrl] = None
    published: bool = True
