"""
Luxury Product Seed Data for PRISM Demo

Contains 15 realistic products spanning three luxury houses:
- Gucci (5 products): bags, ready-to-wear, shoes, accessories
- Louis Vuitton (5 products): bags, shoes, accessories
- Burberry (5 products): outerwear, bags, accessories, ready-to-wear

Each product dict is structured to be directly consumed by IngestProductCommand.
Prices are in EUR. SKU patterns follow brand conventions.
"""

from __future__ import annotations

LUXURY_PRODUCTS: list[dict] = [
    # ─────────────────────────────────────────────────────────────────────
    # GUCCI
    # ─────────────────────────────────────────────────────────────────────
    {
        "tenant_id": "gucci",
        "sku": "GUCCI-BAG-001",
        "name": "GG Marmont Matelassé Shoulder Bag",
        "brand": "Gucci",
        "description": (
            "A structured shoulder bag with the House's distinctive Double G "
            "hardware. Crafted from chevron-quilted matelassé leather with a "
            "softly structured shape. The flap closure opens to a silk lining "
            "with an interior zip pocket. Finished with an antique gold-toned "
            "chain strap that can be worn on the shoulder or cross-body."
        ),
        "category": "Bags",
        "subcategory": "Shoulder Bags",
        "attributes": {
            "material": "matelassé leather",
            "colour": "dusty pink",
            "colour_family": "pink",
            "pattern": "chevron quilted",
            "hardware": "antique gold-toned",
            "lining": "silk",
            "closure": "flap with spring closure",
            "strap_type": "chain",
            "country_of_origin": "Italy",
            "collection": "GG Marmont",
            "season": "AW25",
        },
        "image_uris": [
            "gs://prism-demo/gucci/gg-marmont-shoulder-front.jpg",
            "gs://prism-demo/gucci/gg-marmont-shoulder-side.jpg",
            "gs://prism-demo/gucci/gg-marmont-shoulder-detail.jpg",
            "gs://prism-demo/gucci/gg-marmont-shoulder-interior.jpg",
        ],
        "price_amount": 2450.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.BAG.SHOULDER.STRUCTURED"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "gucci",
        "sku": "GUCCI-BAG-002",
        "name": "Gucci Horsebit 1955 Mini Bag",
        "brand": "Gucci",
        "description": (
            "A compact mini bag featuring the iconic Horsebit hardware, first "
            "introduced in 1955 and reimagined for today. Crafted from GG Supreme "
            "canvas with brown leather trim. The structured silhouette pairs a "
            "removable leather strap with a detachable gold chain for versatile "
            "styling. Interior features a suede lining and one open pocket."
        ),
        "category": "Bags",
        "subcategory": "Mini Bags",
        "attributes": {
            "material": "GG Supreme canvas, leather trim",
            "colour": "ebony/beige",
            "colour_family": "brown",
            "pattern": "GG monogram",
            "hardware": "gold-toned horsebit",
            "lining": "suede",
            "closure": "flap with hook",
            "strap_type": "leather and chain, detachable",
            "country_of_origin": "Italy",
            "collection": "Horsebit 1955",
            "season": "SS25",
        },
        "image_uris": [
            "gs://prism-demo/gucci/horsebit-1955-mini-front.jpg",
            "gs://prism-demo/gucci/horsebit-1955-mini-back.jpg",
            "gs://prism-demo/gucci/horsebit-1955-mini-detail.jpg",
        ],
        "price_amount": 1890.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.BAG.MINI.STRUCTURED"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "gucci",
        "sku": "GUCCI-RTW-001",
        "name": "Gucci Flora Gorgeous Gardenia Silk Dress",
        "brand": "Gucci",
        "description": (
            "A flowing midi dress in the Flora print, originally designed for "
            "Grace Kelly in 1966 and reimagined with lush Gardenia motifs. "
            "Cut from fluid silk twill with a gathered waist, flutter sleeves, "
            "and a gently flared skirt. The print features hand-illustrated "
            "botanicals in soft pastel tones against an ivory ground."
        ),
        "category": "Ready-to-Wear",
        "subcategory": "Dresses",
        "attributes": {
            "material": "silk twill",
            "material_composition": "100% silk",
            "colour": "ivory with pastel florals",
            "colour_family": "white",
            "pattern": "Flora Gorgeous Gardenia print",
            "silhouette": "A-line midi",
            "fit": "fitted waist, flared skirt",
            "occasion": "evening, garden party",
            "season": "SS25",
            "care_instructions": "dry clean only",
            "country_of_origin": "Italy",
            "available_sizes": "38,40,42,44,46",
            "size_system": "IT",
        },
        "image_uris": [
            "gs://prism-demo/gucci/flora-gardenia-dress-front.jpg",
            "gs://prism-demo/gucci/flora-gardenia-dress-back.jpg",
            "gs://prism-demo/gucci/flora-gardenia-dress-detail.jpg",
            "gs://prism-demo/gucci/flora-gardenia-dress-runway.jpg",
        ],
        "price_amount": 3200.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.RTW.DRESS.MIDI", "LUX.RTW.DRESS.EVENING"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "gucci",
        "sku": "GUCCI-SHO-001",
        "name": "Gucci Ace Embroidered Sneakers",
        "brand": "Gucci",
        "description": (
            "The iconic Gucci Ace sneaker in soft white leather, adorned with "
            "the House's signature embroidered bee motif on each side. Features "
            "the classic Web stripe in green and red along the heel, a padded "
            "collar for comfort, and a natural rubber sole. A staple of the "
            "Gucci sneaker collection since its debut."
        ),
        "category": "Shoes",
        "subcategory": "Sneakers",
        "attributes": {
            "material": "leather",
            "colour": "white with bee embroidery",
            "colour_family": "white",
            "pattern": "embroidered bee, Web stripe",
            "sole": "natural rubber",
            "fit": "regular",
            "occasion": "casual, smart casual",
            "season": "all seasons",
            "care_instructions": "wipe with damp cloth",
            "country_of_origin": "Italy",
            "available_sizes": "35,36,37,38,39,40,41,42,43,44,45",
            "size_system": "EU",
        },
        "image_uris": [
            "gs://prism-demo/gucci/ace-sneakers-side.jpg",
            "gs://prism-demo/gucci/ace-sneakers-top.jpg",
            "gs://prism-demo/gucci/ace-sneakers-detail.jpg",
        ],
        "price_amount": 720.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.SHO.SNEAKER.LOW"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "gucci",
        "sku": "GUCCI-ACC-001",
        "name": "Gucci GG Supreme Canvas Belt",
        "brand": "Gucci",
        "description": (
            "A refined belt in GG Supreme canvas with brown leather trim and the "
            "iconic interlocking G buckle in shiny gold-toned metal. The classic "
            "monogram pattern is rendered in a subtle beige and ebony colourway. "
            "Width: 3 cm. The belt is adjustable and presented in a Gucci "
            "dust bag and branded box."
        ),
        "category": "Accessories",
        "subcategory": "Belts",
        "attributes": {
            "material": "GG Supreme canvas, leather",
            "colour": "beige/ebony",
            "colour_family": "brown",
            "pattern": "GG monogram",
            "hardware": "shiny gold-toned interlocking G",
            "width": "3 cm",
            "country_of_origin": "Italy",
            "season": "all seasons",
        },
        "image_uris": [
            "gs://prism-demo/gucci/gg-supreme-belt-front.jpg",
            "gs://prism-demo/gucci/gg-supreme-belt-buckle.jpg",
        ],
        "price_amount": 450.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.ACC.BELT"],
        "source": "ucp_feed",
    },
    # ─────────────────────────────────────────────────────────────────────
    # LOUIS VUITTON
    # ─────────────────────────────────────────────────────────────────────
    {
        "tenant_id": "louis-vuitton",
        "sku": "LV-BAG-001",
        "name": "Neverfull MM Monogram",
        "brand": "Louis Vuitton",
        "description": (
            "The iconic Neverfull tote in Monogram canvas, a timeless staple of "
            "the Louis Vuitton collection. The generous interior features a "
            "removable zippered pochette that doubles as a clutch. Slim leather "
            "side straps allow the bag to be cinched for a sleeker silhouette or "
            "loosened for a casual, open shape. Textile lining with a coloured "
            "interior. Made in France."
        ),
        "category": "Bags",
        "subcategory": "Totes",
        "attributes": {
            "material": "Monogram coated canvas, natural cowhide trim",
            "colour": "Monogram brown",
            "colour_family": "brown",
            "pattern": "LV Monogram",
            "lining": "textile, striped",
            "closure": "open top with side straps",
            "dimensions": "31 x 28 x 14 cm",
            "country_of_origin": "France",
            "collection": "Monogram",
            "season": "timeless",
            "care_instructions": "store in dust bag, avoid prolonged sun exposure",
        },
        "image_uris": [
            "gs://prism-demo/louis-vuitton/neverfull-mm-front.jpg",
            "gs://prism-demo/louis-vuitton/neverfull-mm-side.jpg",
            "gs://prism-demo/louis-vuitton/neverfull-mm-interior.jpg",
            "gs://prism-demo/louis-vuitton/neverfull-mm-pochette.jpg",
        ],
        "price_amount": 1590.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.BAG.TOTE.OPEN"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "louis-vuitton",
        "sku": "LV-BAG-002",
        "name": "Capucines BB",
        "brand": "Louis Vuitton",
        "description": (
            "Named after the Rue des Capucines in Paris, where Louis Vuitton opened "
            "his first store in 1854. This exquisite handbag is crafted from full-grain "
            "Taurillon leather with a refined, structured silhouette. The jewel-like LV "
            "initials on the flap can be tucked inside for a minimalist look. Hand-painted "
            "edges and a microfibre lining with multiple compartments. Made in France."
        ),
        "category": "Bags",
        "subcategory": "Top Handle Bags",
        "attributes": {
            "material": "Taurillon leather",
            "colour": "noir",
            "colour_family": "black",
            "pattern": "solid",
            "hardware": "silver-colour metallic pieces",
            "lining": "microfibre",
            "closure": "flap with magnetic closure",
            "dimensions": "27 x 18 x 9 cm",
            "country_of_origin": "France",
            "collection": "Capucines",
            "season": "timeless",
            "care_instructions": "avoid contact with water, store in dust bag",
        },
        "image_uris": [
            "gs://prism-demo/louis-vuitton/capucines-bb-front.jpg",
            "gs://prism-demo/louis-vuitton/capucines-bb-side.jpg",
            "gs://prism-demo/louis-vuitton/capucines-bb-interior.jpg",
            "gs://prism-demo/louis-vuitton/capucines-bb-detail.jpg",
        ],
        "price_amount": 5200.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.BAG.TOPHANDLE.STRUCTURED"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "louis-vuitton",
        "sku": "LV-SHO-001",
        "name": "LV Archlight Sneaker",
        "brand": "Louis Vuitton",
        "description": (
            "A bold, futuristic sneaker inspired by archival running shoe designs. "
            "The oversized, curved outsole creates the signature wave silhouette. "
            "Constructed with a mix of technical fabrics and calf leather, featuring "
            "the LV monogram on the tongue and heel counter. A statement piece that "
            "blends sportswear engineering with haute couture sensibility."
        ),
        "category": "Shoes",
        "subcategory": "Sneakers",
        "attributes": {
            "material": "technical fabric, calf leather",
            "colour": "white/silver",
            "colour_family": "white",
            "pattern": "LV monogram details",
            "sole": "oversized rubber, wave silhouette",
            "fit": "regular",
            "occasion": "casual, streetwear",
            "season": "all seasons",
            "care_instructions": "wipe clean with soft cloth",
            "country_of_origin": "Italy",
            "available_sizes": "35,36,37,38,39,40,41,42,43,44",
            "size_system": "EU",
        },
        "image_uris": [
            "gs://prism-demo/louis-vuitton/archlight-sneaker-side.jpg",
            "gs://prism-demo/louis-vuitton/archlight-sneaker-back.jpg",
            "gs://prism-demo/louis-vuitton/archlight-sneaker-sole.jpg",
        ],
        "price_amount": 1090.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.SHO.SNEAKER.HIGH"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "louis-vuitton",
        "sku": "LV-ACC-001",
        "name": "Monogram Silk Scarf",
        "brand": "Louis Vuitton",
        "description": (
            "A luxurious square scarf in pure silk twill, printed with the iconic "
            "Louis Vuitton Monogram motif in a contemporary gradient colourway. "
            "Hand-rolled edges lend an artisanal finish. Can be worn around the neck, "
            "as a headband, or tied to a bag as a decorative accent. "
            "Dimensions: 90 x 90 cm. Made in Italy."
        ),
        "category": "Accessories",
        "subcategory": "Scarves",
        "attributes": {
            "material": "silk twill",
            "material_composition": "100% silk",
            "colour": "gradient blue to pink",
            "colour_family": "blue",
            "pattern": "LV Monogram",
            "dimensions": "90 x 90 cm",
            "country_of_origin": "Italy",
            "season": "SS25",
            "care_instructions": "dry clean only",
        },
        "image_uris": [
            "gs://prism-demo/louis-vuitton/monogram-silk-scarf-flat.jpg",
            "gs://prism-demo/louis-vuitton/monogram-silk-scarf-styled.jpg",
        ],
        "price_amount": 495.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.ACC.SCARF.SILK"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "louis-vuitton",
        "sku": "LV-BAG-003",
        "name": "Keepall 50 Bandouliere",
        "brand": "Louis Vuitton",
        "description": (
            "The legendary travel companion in Monogram canvas. Originally created "
            "in 1930, the Keepall has defined the art of elegant travel for nearly "
            "a century. This Bandouliere version includes a detachable, adjustable "
            "shoulder strap with a leather pad for comfort. Natural cowhide handles "
            "and trim develop a rich patina over time. Padlock and keys included. "
            "Cabin-friendly size: 50 x 29 x 23 cm. Made in France."
        ),
        "category": "Bags",
        "subcategory": "Travel Bags",
        "attributes": {
            "material": "Monogram coated canvas, natural cowhide trim",
            "colour": "Monogram brown",
            "colour_family": "brown",
            "pattern": "LV Monogram",
            "hardware": "golden brass",
            "closure": "double zip with padlock",
            "dimensions": "50 x 29 x 23 cm",
            "strap_type": "detachable shoulder strap with pad",
            "country_of_origin": "France",
            "collection": "Monogram Travel",
            "season": "timeless",
            "care_instructions": "store flat, leather develops natural patina",
            "occasion": "travel, weekend",
        },
        "image_uris": [
            "gs://prism-demo/louis-vuitton/keepall-50-front.jpg",
            "gs://prism-demo/louis-vuitton/keepall-50-side.jpg",
            "gs://prism-demo/louis-vuitton/keepall-50-interior.jpg",
            "gs://prism-demo/louis-vuitton/keepall-50-lock.jpg",
        ],
        "price_amount": 2170.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.BAG.TRAVEL.DUFFLE"],
        "source": "ucp_feed",
    },
    # ─────────────────────────────────────────────────────────────────────
    # BURBERRY
    # ─────────────────────────────────────────────────────────────────────
    {
        "tenant_id": "burberry",
        "sku": "BURB-RTW-001",
        "name": "Kensington Heritage Trench Coat",
        "brand": "Burberry",
        "description": (
            "The definitive Burberry trench coat, cut in Kensington fit from "
            "weatherproof cotton gabardine — a fabric invented by Thomas Burberry "
            "in 1879. Features the signature check lining, storm shield, gun flap, "
            "and D-ring belt. Every detail references the coat's military heritage: "
            "epaulettes for holding gloves, a chin warmer strap, and a hooked "
            "throat latch. Unlined sleeves for a lighter feel. Made in England."
        ),
        "category": "Ready-to-Wear",
        "subcategory": "Outerwear",
        "attributes": {
            "material": "cotton gabardine",
            "material_composition": "100% cotton, check lining: 100% cotton",
            "colour": "honey",
            "colour_family": "beige",
            "pattern": "solid exterior, Vintage Check lining",
            "silhouette": "mid-length, tailored",
            "fit": "Kensington (classic)",
            "occasion": "everyday, business, formal",
            "season": "AW25, SS25",
            "care_instructions": "specialist dry clean",
            "country_of_origin": "England",
            "available_sizes": "44,46,48,50,52,54,56",
            "size_system": "IT",
        },
        "image_uris": [
            "gs://prism-demo/burberry/kensington-trench-front.jpg",
            "gs://prism-demo/burberry/kensington-trench-back.jpg",
            "gs://prism-demo/burberry/kensington-trench-detail.jpg",
            "gs://prism-demo/burberry/kensington-trench-lining.jpg",
        ],
        "price_amount": 2190.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.RTW.OUTERWEAR.TRENCH"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "burberry",
        "sku": "BURB-BAG-001",
        "name": "TB Monogram Leather Bag",
        "brand": "Burberry",
        "description": (
            "A structured shoulder bag featuring the Thomas Burberry Monogram "
            "clasp in antique brass. Crafted from smooth Italian calf leather "
            "with a cotton canvas lining. The two-strap design allows it to be "
            "carried by hand or worn on the shoulder. Interior features a slip "
            "pocket and zip pocket. A modern interpretation of archival Burberry "
            "hardware details."
        ),
        "category": "Bags",
        "subcategory": "Shoulder Bags",
        "attributes": {
            "material": "smooth calf leather",
            "colour": "malt brown",
            "colour_family": "brown",
            "pattern": "solid",
            "hardware": "antique brass TB monogram clasp",
            "lining": "cotton canvas",
            "closure": "clasp",
            "country_of_origin": "Italy",
            "collection": "TB Monogram",
            "season": "AW25",
        },
        "image_uris": [
            "gs://prism-demo/burberry/tb-leather-bag-front.jpg",
            "gs://prism-demo/burberry/tb-leather-bag-side.jpg",
            "gs://prism-demo/burberry/tb-leather-bag-clasp.jpg",
        ],
        "price_amount": 1690.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.BAG.SHOULDER.STRUCTURED"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "burberry",
        "sku": "BURB-ACC-001",
        "name": "Vintage Check Cashmere Scarf",
        "brand": "Burberry",
        "description": (
            "The quintessential Burberry scarf, woven from the softest Scottish "
            "cashmere at a heritage mill in Elgin, Scotland. Features the iconic "
            "Vintage Check pattern in camel, red, black, and white. Finished with "
            "hand-tied fringing. A piece that has defined understated British "
            "luxury for over a century. Dimensions: 168 x 30 cm."
        ),
        "category": "Accessories",
        "subcategory": "Scarves",
        "attributes": {
            "material": "cashmere",
            "material_composition": "100% cashmere",
            "colour": "archive beige",
            "colour_family": "beige",
            "pattern": "Vintage Check",
            "dimensions": "168 x 30 cm",
            "country_of_origin": "Scotland",
            "season": "AW25",
            "care_instructions": "dry clean only, store folded",
        },
        "image_uris": [
            "gs://prism-demo/burberry/vintage-check-scarf-flat.jpg",
            "gs://prism-demo/burberry/vintage-check-scarf-styled.jpg",
            "gs://prism-demo/burberry/vintage-check-scarf-fringe.jpg",
        ],
        "price_amount": 520.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.ACC.SCARF.CASHMERE"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "burberry",
        "sku": "BURB-BAG-002",
        "name": "Knight Large Leather Bag",
        "brand": "Burberry",
        "description": (
            "A statement handbag from Burberry's Knight collection, inspired by "
            "equestrian traditions. Crafted from supple Italian leather with a "
            "rounded silhouette and a distinctive shield-shaped lock closure. "
            "The woven leather strap adds artisanal texture. Interior features "
            "multiple compartments and a detachable mirror. A commanding piece "
            "that balances heritage references with contemporary proportion."
        ),
        "category": "Bags",
        "subcategory": "Top Handle Bags",
        "attributes": {
            "material": "Italian leather",
            "colour": "black",
            "colour_family": "black",
            "pattern": "solid",
            "hardware": "palladium shield lock",
            "lining": "suede",
            "closure": "shield lock",
            "strap_type": "woven leather, detachable cross-body",
            "country_of_origin": "Italy",
            "collection": "Knight",
            "season": "AW25",
            "occasion": "everyday, business",
        },
        "image_uris": [
            "gs://prism-demo/burberry/knight-large-front.jpg",
            "gs://prism-demo/burberry/knight-large-side.jpg",
            "gs://prism-demo/burberry/knight-large-detail.jpg",
            "gs://prism-demo/burberry/knight-large-interior.jpg",
        ],
        "price_amount": 2890.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.BAG.TOPHANDLE.STRUCTURED"],
        "source": "ucp_feed",
    },
    {
        "tenant_id": "burberry",
        "sku": "BURB-RTW-002",
        "name": "Archive Beige Check Shirt",
        "brand": "Burberry",
        "description": (
            "A relaxed-fit shirt in Burberry's archive beige check pattern, "
            "printed on lightweight cotton poplin. Features a spread collar, "
            "single chest pocket, and curved hem. The check is rendered in a "
            "tonal palette that nods to the Haymarket check introduced in the "
            "1920s. An effortless piece that bridges casual and smart dressing."
        ),
        "category": "Ready-to-Wear",
        "subcategory": "Shirts",
        "attributes": {
            "material": "cotton poplin",
            "material_composition": "100% cotton",
            "colour": "archive beige check",
            "colour_family": "beige",
            "pattern": "Burberry Check",
            "silhouette": "relaxed",
            "fit": "relaxed",
            "occasion": "casual, smart casual",
            "season": "SS25",
            "care_instructions": "machine wash at 30 degrees",
            "country_of_origin": "Portugal",
            "available_sizes": "XS,S,M,L,XL,XXL",
            "size_system": "INT",
        },
        "image_uris": [
            "gs://prism-demo/burberry/archive-check-shirt-front.jpg",
            "gs://prism-demo/burberry/archive-check-shirt-back.jpg",
            "gs://prism-demo/burberry/archive-check-shirt-detail.jpg",
        ],
        "price_amount": 590.00,
        "price_currency": "EUR",
        "taxonomy_codes": ["LUX.RTW.SHIRT.CASUAL"],
        "source": "ucp_feed",
    },
]
"""
Complete luxury product catalogue for PRISM demo.

All 15 products are structured for IngestProductCommand consumption.
Products span three luxury houses with realistic attributes, pricing, and imagery.
"""


def get_products_for_tenant(tenant_id: str) -> list[dict]:
    """
    Filter products by tenant ID.

    Args:
        tenant_id: The tenant identifier (e.g. "gucci", "louis-vuitton", "burberry").

    Returns:
        List of product dicts belonging to the specified tenant.
    """
    return [p for p in LUXURY_PRODUCTS if p["tenant_id"] == tenant_id]
