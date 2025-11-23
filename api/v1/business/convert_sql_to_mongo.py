import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import mysql.connector
from mysql.connector import MySQLConnection
from phpserialize import phpobject, loads as php_unserialize

# Import cleaner từ product_description_cleaner
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from controllers.ultils.product_description_cleaner import cleaner


@dataclass
class Pricing:
    price: Optional[float] = None
    currency: Optional[str] = None
    cost: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "currency": self.currency,
            "cost": self.cost,
        }


@dataclass
class Media:
    type: str
    url: str
    alt_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": self.type,
            "url": self.url,
        }
        if self.alt_text:
            payload["alt_text"] = self.alt_text
        return payload


@dataclass
class Product:
    product_id: int
    name: str
    sku: Optional[str]
    pricing: Pricing
    company_id: Optional[str] = None
    media: List[Media] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    quantity: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name,
            "sku": self.sku,
            "pricing": self.pricing.to_dict(),
        }
        if self.media:
            payload["media"] = [medium.to_dict() for medium in self.media]
        if self.company_id:
            payload["company_id"] = self.company_id
        if self.data:
            payload["data"] = self.data
        if self.quantity is not None:
            payload["quantity"] = self.quantity
        return payload


def chunked(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    if size <= 0:
        raise ValueError("size must be positive")
    for start in range(0, len(items), size):
        yield items[start:start + size]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export WooCommerce product data to JSON")
    parser.add_argument("--host", default="144.91.113.233", help="MySQL host")
    parser.add_argument("--port", default=3306, type=int, help="MySQL port")
    parser.add_argument("--user", default="mekongai", help="MySQL username")
    parser.add_argument("--password", default="12345678", help="MySQL password")
    parser.add_argument("--database", default="test_kat", help="MySQL database name")
    parser.add_argument("--table-prefix", default="wg_", help="WordPress table prefix (default: wg_)")
    parser.add_argument("--output", default="products.json", help="Output JSON file path")
    parser.add_argument("--status", nargs="*", default=["publish", "draft", "pending", "private"],
                        help="Post statuses to include (default: publish draft pending private)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Optional limit on number of products to export")
    return parser.parse_args()


def open_connection(args: argparse.Namespace) -> MySQLConnection:
    return mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        use_pure=True,
    )


def fetch_default_currency(conn: MySQLConnection, prefix: str) -> Optional[str]:
    query = f"SELECT option_value FROM {prefix}options WHERE option_name = %s"
    with conn.cursor(dictionary=True) as cursor:
        cursor.execute(query, ("woocommerce_currency",))
        row = cursor.fetchone()
        return row["option_value"] if row else None


def fetch_products(conn: MySQLConnection, prefix: str, statuses: Sequence[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    placeholders = ",".join(["%s"] * len(statuses))
    query = [
        f"SELECT ID, post_title, post_content, post_excerpt",
        f"FROM {prefix}posts",
        "WHERE post_type = 'product'",
        f"AND post_status IN ({placeholders})",
        "ORDER BY ID ASC",
    ]
    if limit:
        query.append("LIMIT %s")
    sql = " ".join(query)
    with conn.cursor(dictionary=True) as cursor:
        params: List[Any] = list(statuses)
        if limit:
            params.append(limit)
        cursor.execute(sql, params)
        return cursor.fetchall()


def fetch_meta(conn: MySQLConnection, prefix: str, product_ids: Sequence[int], meta_keys: Sequence[str]) -> Dict[int, Dict[str, str]]:
    if not product_ids:
        return {}
    result: Dict[int, Dict[str, str]] = defaultdict(dict)
    meta_in = ",".join(["%s"] * len(meta_keys))
    for batch in chunked(list(product_ids), 2000):
        placeholders = ",".join(["%s"] * len(batch))
        query = (
            f"SELECT post_id, meta_key, meta_value FROM {prefix}postmeta "
            f"WHERE post_id IN ({placeholders}) AND meta_key IN ({meta_in})"
        )
        params = list(batch) + list(meta_keys)
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params)
            for row in cursor:
                result[row["post_id"]][row["meta_key"]] = row["meta_value"]
    return result


def fetch_all_meta(conn: MySQLConnection, prefix: str, product_ids: Sequence[int]) -> Dict[int, Dict[str, List[str]]]:
    """Fetch every meta key for a product (used for fallbacks like company_id)."""
    if not product_ids:
        return {}
    result: Dict[int, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for batch in chunked(list(product_ids), 2000):
        placeholders = ",".join(["%s"] * len(batch))
        query = f"SELECT post_id, meta_key, meta_value FROM {prefix}postmeta WHERE post_id IN ({placeholders})"
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, list(batch))
            for row in cursor:
                result[row["post_id"]][row["meta_key"]].append(row["meta_value"])
    return result


def fetch_taxonomy_terms(conn: MySQLConnection, prefix: str, product_ids: Sequence[int]) -> Dict[int, Dict[str, List[Dict[str, str]]]]:
    if not product_ids:
        return {}
    result: Dict[int, Dict[str, List[Dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for batch in chunked(list(product_ids), 2000):
        placeholders = ",".join(["%s"] * len(batch))
        query = (
            f"SELECT tr.object_id AS product_id, tt.taxonomy, t.name, t.slug "
            f"FROM {prefix}term_relationships tr "
            f"JOIN {prefix}term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id "
            f"JOIN {prefix}terms t ON t.term_id = tt.term_id "
            f"WHERE tr.object_id IN ({placeholders})"
        )
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, list(batch))
            for row in cursor:
                payload = {"name": row["name"], "slug": row["slug"]}
                result[row["product_id"]][row["taxonomy"]].append(payload)
    return result


def fetch_media_posts(conn: MySQLConnection, prefix: str, media_ids: Sequence[int]) -> Dict[int, Dict[str, Any]]:
    if not media_ids:
        return {}
    media_map: Dict[int, Dict[str, Any]] = {}
    for batch in chunked(list(media_ids), 2000):
        placeholders = ",".join(["%s"] * len(batch))
        query = (
            f"SELECT ID, post_title, post_mime_type, guid "
            f"FROM {prefix}posts WHERE ID IN ({placeholders})"
        )
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, list(batch))
            for row in cursor:
                media_map[row["ID"]] = row
    return media_map


def fetch_media_alt_text(conn: MySQLConnection, prefix: str, media_ids: Sequence[int]) -> Dict[int, str]:
    if not media_ids:
        return {}
    alt_map: Dict[int, str] = {}
    for batch in chunked(list(media_ids), 2000):
        placeholders = ",".join(["%s"] * len(batch))
        query = (
            f"SELECT post_id, meta_value FROM {prefix}postmeta "
            f"WHERE post_id IN ({placeholders}) AND meta_key = %s"
        )
        params = list(batch) + ["_wp_attachment_image_alt"]
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params)
            for row in cursor:
                alt_map[row["post_id"]] = row["meta_value"]
    return alt_map


def fetch_product_meta_lookup(conn: MySQLConnection, prefix: str, product_ids: Sequence[int]) -> Dict[int, Dict[str, Any]]:
    if not product_ids:
        return {}
    result: Dict[int, Dict[str, Any]] = {}
    table = f"{prefix}wc_product_meta_lookup"
    columns = [
        "product_id",
        "stock_quantity",
        "stock_status",
    ]
    column_sql = ", ".join(columns)
    for batch in chunked(list(product_ids), 2000):
        placeholders = ",".join(["%s"] * len(batch))
        query = f"SELECT {column_sql} FROM {table} WHERE product_id IN ({placeholders})"
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, list(batch))
            for row in cursor:
                result[row["product_id"]] = row
    return result


def safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        cleaned = value.strip()
        if not cleaned:
            return None
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def parse_php_serialized(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        decoded = php_unserialize(value.encode("utf-8"), decode_strings=True)
    except Exception:
        return {}
    if isinstance(decoded, dict):
        return _convert_php_structure(decoded)
    return {}


def _convert_php_structure(data: Any) -> Any:
    if isinstance(data, dict):
        converted: Dict[str, Any] = {}
        for key, val in data.items():
            if isinstance(key, bytes):
                key = key.decode("utf-8", errors="ignore")
            converted[key] = _convert_php_structure(val)
        return converted
    if isinstance(data, (list, tuple)):
        return [_convert_php_structure(item) for item in data]
    if isinstance(data, phpobject):
        return {
            "__php_class__": data.__phpclass__ if hasattr(data, "__phpclass__") else None,
            "__data__": _convert_php_structure(data._asdict()),
        }
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="ignore")
    return data


def extract_attributes(meta: Dict[str, str], taxonomy_map: Dict[str, List[Dict[str, str]]]) -> Dict[str, Any]:
    attributes: Dict[str, Any] = {}
    serialized = meta.get("_product_attributes")
    parsed = parse_php_serialized(serialized)
    if parsed:
        for attr_key, attr_data in parsed.items():
            if not isinstance(attr_data, dict):
                continue
            label = attr_data.get("name", attr_key)
            options: List[str] = []
            values = attr_data.get("value")
            if isinstance(values, str):
                options = [item.strip() for item in values.split("|") if item.strip()]
            elif isinstance(values, (list, tuple)):
                options = [str(item) for item in values]
            if not options and attr_key in taxonomy_map:
                options = [term["name"] for term in taxonomy_map[attr_key]]
            if options:
                attributes[label] = options
    # Include taxonomy-derived attributes (pa_*)
    for taxonomy, terms in taxonomy_map.items():
        if taxonomy.startswith("pa_"):
            human_name = taxonomy.replace("pa_", "").replace("_", " ")
            if human_name not in attributes:
                attributes[human_name] = [term["name"] for term in terms]
    return attributes


def build_media_list(meta: Dict[str, str], media_lookup: Dict[int, Dict[str, Any]], alt_lookup: Dict[int, str]) -> List[Media]:
    media_ids: List[int] = []
    featured_id = meta.get("_thumbnail_id")
    if featured_id and featured_id.isdigit():
        media_ids.append(int(featured_id))
    gallery_ids = meta.get("_product_image_gallery")
    if gallery_ids:
        media_ids.extend(
            int(media_id) for media_id in gallery_ids.split(",") if media_id.strip().isdigit()
        )
    seen: set[int] = set()
    media_entries: List[Media] = []
    for media_id in media_ids:
        if media_id in seen:
            continue
        seen.add(media_id)
        media_post = media_lookup.get(media_id)
        if not media_post:
            continue
        mime = (media_post.get("post_mime_type") or "").lower()
        media_type = "image" if mime.startswith("image/") else "video" if mime.startswith("video/") else "file"
        url = media_post.get("guid") or ""
        if not url:
            continue
        alt_text = alt_lookup.get(media_id)
        media_entries.append(Media(type=media_type, url=url, alt_text=alt_text))
    return media_entries


def resolve_currency(meta: Dict[str, str], default_currency: Optional[str]) -> Optional[str]:
    for candidate in (meta.get("_currency"), default_currency):
        if candidate:
            return candidate
    return None


def select_cost(meta: Dict[str, str]) -> Optional[float]:
    for key in ("_wc_cog_cost", "_alg_wc_cog_cost", "_cost", "_purchase_price"):
        value = meta.get(key)
        cleaned = safe_float(value)
        if cleaned is not None:
            return cleaned
    regular_price = safe_float(meta.get("_regular_price"))
    if regular_price is not None:
        return regular_price
    return None


def select_price(meta: Dict[str, str]) -> Optional[float]:
    for key in ("_price", "_regular_price", "_sale_price"):
        value = meta.get(key)
        cleaned = safe_float(value)
        if cleaned is not None:
            return cleaned
    return None

def select_quantity(meta: Dict[str, str], lookup: Optional[Dict[str, Any]]) -> Optional[float]:
    stock = safe_float(meta.get("_stock"))
    manage_stock = (meta.get("_manage_stock") or "").lower() in {"yes", "1", "true"}
    if stock is not None and (manage_stock or meta.get("_stock") is not None):
        return stock
    if lookup:
        lookup_stock = lookup.get("stock_quantity")
        if lookup_stock is not None:
            try:
                return float(lookup_stock)
            except (ValueError, TypeError):
                pass
    status = meta.get("_stock_status")
    if not status and lookup:
        status = lookup.get("stock_status")
    if status:
        return 0.0 if status != "instock" else 0.0
    return 0.0


def coalesce_meta(meta: Dict[str, List[str]], key: str) -> Optional[str]:
    values = meta.get(key)
    if not values:
        return None
    return values[0]


def main() -> None:
    args = parse_args()
    conn = open_connection(args)
    try:
        prefix = args.table_prefix
        statuses = args.status
        products = fetch_products(conn, prefix, statuses, args.limit)
        if not products:
            print("No products found for the specified criteria.")
            return

        product_ids = [row["ID"] for row in products]

        meta_keys = [
            "_sku",
            "_price",
            "_regular_price",
            "_sale_price",
            "_wc_cog_cost",
            "_alg_wc_cog_cost",
            "_cost",
            "_purchase_price",
            "_currency",
            "_thumbnail_id",
            "_product_image_gallery",
            "_weight",
            "_length",
            "_width",
            "_height",
            "_product_attributes",
            "_stock",
            "_manage_stock",
            "_stock_status",
            "company_id",
        ]

        meta_lookup = fetch_meta(conn, prefix, product_ids, meta_keys)
        full_meta_lookup = fetch_all_meta(conn, prefix, product_ids)
        taxonomy_lookup = fetch_taxonomy_terms(conn, prefix, product_ids)
        product_meta_lookup = fetch_product_meta_lookup(conn, prefix, product_ids)

        media_ids = set()
        for meta in meta_lookup.values():
            thumb = meta.get("_thumbnail_id")
            if thumb and thumb.isdigit():
                media_ids.add(int(thumb))
            gallery = meta.get("_product_image_gallery")
            if gallery:
                media_ids.update(int(mid) for mid in gallery.split(",") if mid.strip().isdigit())
        media_lookup = fetch_media_posts(conn, prefix, list(media_ids))
        alt_lookup = fetch_media_alt_text(conn, prefix, list(media_ids))

        default_currency = fetch_default_currency(conn, prefix)

        exported: List[Dict[str, Any]] = []

        for product in products:
            product_id = product["ID"]
            meta = meta_lookup.get(product_id, {})
            all_meta = full_meta_lookup.get(product_id, {})
            taxonomies = taxonomy_lookup.get(product_id, {})

            raw_sku = meta.get("_sku")
            sku = raw_sku.strip() if raw_sku else str(product_id)
            product_lookup_row = product_meta_lookup.get(product_id)
            pricing = Pricing(
                price=select_price(meta),
                currency=resolve_currency(meta, default_currency),
                cost=select_cost(meta),
            )
            quantity = select_quantity(meta, product_lookup_row)

            media_entries = build_media_list(meta, media_lookup, alt_lookup)

            categories = [term["name"] for term in taxonomies.get("product_cat", [])]
            tags = [term["name"] for term in taxonomies.get("product_tag", [])]
            colors = [term["name"] for term in taxonomies.get("pa_color", [])]
            sizes = [term["name"] for term in taxonomies.get("pa_size", [])]

            dimensions = {
                "length": safe_float(meta.get("_length")),
                "width": safe_float(meta.get("_width")),
                "height": safe_float(meta.get("_height")),
            }
            dimensions = {k: v for k, v in dimensions.items() if v is not None}

            data_payload: Dict[str, Any] = {}
            if product.get("post_content"):
                # Clean description trước khi lưu vào database
                raw_description = product["post_content"].strip()
                cleaned_description = cleaner.clean_description(raw_description)
                data_payload["description"] = cleaned_description
            if categories:
                data_payload["category"] = categories
            if safe_float(meta.get("_weight")) is not None:
                data_payload["weight"] = safe_float(meta.get("_weight"))
            if dimensions:
                data_payload["dimensions"] = dimensions
            if colors:
                data_payload["color"] = ", ".join(colors)
            if sizes:
                data_payload["size"] = ", ".join(sizes)
            if tags:
                data_payload["tags"] = tags

            attributes = extract_attributes(meta, taxonomies)
            if attributes:
                data_payload["attributes"] = attributes

            company_id = meta.get("company_id") or coalesce_meta(all_meta, "company_id")
            if company_id:
                company_id = company_id.strip() or None

            product_payload = Product(
                product_id=product_id,
                name=product["post_title"],
                sku=sku,
                pricing=pricing,
                company_id=company_id,
                media=media_entries,
                data=data_payload,
                quantity=quantity,
            )
            exported.append(product_payload.to_dict())

        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(exported, fp, ensure_ascii=False, indent=2)
        print(f"Exported {len(exported)} products to {args.output}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
