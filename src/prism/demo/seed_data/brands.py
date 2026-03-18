"""
Brand Definitions for PRISM Demo

Provides brand configuration data for three luxury houses:
- Gucci (Kering Group)
- Louis Vuitton (LVMH)
- Burberry

Each brand includes tone profiles for AI description generation,
supported locales, and brand identity metadata.
"""

from __future__ import annotations

BRANDS: list[dict] = [
    {
        "name": "Gucci",
        "tenant_id": "gucci",
        "description": (
            "Founded in Florence in 1921, Gucci is one of the world's leading luxury "
            "fashion brands. Under the creative vision of Sabato De Sarno, the House "
            "redefines luxury for the 21st century, blending Italian craftsmanship with "
            "eclectic, contemporary aesthetics. Gucci's products represent the pinnacle "
            "of Italian artisanship and are recognised for their quality and attention "
            "to detail."
        ),
        "logo_uri": "gs://prism-demo/brands/gucci/logo.png",
        "locales": [
            {"language": "en", "region": ""},
            {"language": "it", "region": "IT"},
            {"language": "fr", "region": "FR"},
            {"language": "zh", "region": "CN"},
            {"language": "ja", "region": "JP"},
            {"language": "ko", "region": "KR"},
            {"language": "ar", "region": ""},
        ],
        "tone_profile": (
            "Sophisticated yet eclectic. Balance Italian heritage with contemporary "
            "flair. Use evocative, sensorial language that conveys both craftsmanship "
            "and bold self-expression. Reference Florentine artisanship. Emphasise "
            "the interplay of tradition and modernity. Avoid generic luxury adjectives; "
            "prefer specific tactile and visual descriptors. Tone should feel intimate "
            "and knowing, as if speaking to a discerning friend."
        ),
    },
    {
        "name": "Louis Vuitton",
        "tenant_id": "louis-vuitton",
        "description": (
            "Since 1854, Louis Vuitton has perpetually reinvented the art of travel "
            "through its iconic trunks, leather goods, and fashion collections. As "
            "the world's most valuable luxury brand, Louis Vuitton combines tradition "
            "with innovation across every product category. Each piece carries the "
            "spirit of savoir-faire that has defined the Maison for over 170 years."
        ),
        "logo_uri": "gs://prism-demo/brands/louis-vuitton/logo.png",
        "locales": [
            {"language": "en", "region": ""},
            {"language": "fr", "region": "FR"},
            {"language": "zh", "region": "CN"},
            {"language": "ja", "region": "JP"},
            {"language": "ko", "region": "KR"},
            {"language": "ar", "region": ""},
            {"language": "de", "region": "DE"},
        ],
        "tone_profile": (
            "Authoritative and refined. Emphasise the Maison's heritage of travel "
            "and savoir-faire. Language should be precise and elegant, never flashy. "
            "Reference the spirit of journey and exploration. Highlight the exceptional "
            "craftsmanship and materials. Use a measured, confident cadence that "
            "reflects 170 years of uncompromising quality. Descriptions should feel "
            "like a curator narrating a private collection."
        ),
    },
    {
        "name": "Burberry",
        "tenant_id": "burberry",
        "description": (
            "Founded in 1856, Burberry is a global luxury brand with a distinctly "
            "British attitude. Under the creative direction of Daniel Lee, the house "
            "celebrates its heritage of outerwear innovation and the iconic check "
            "pattern while pushing into bold new creative territory. Burberry's "
            "products embody the spirit of exploration and protection against the "
            "elements, reimagined for modern life."
        ),
        "logo_uri": "gs://prism-demo/brands/burberry/logo.png",
        "locales": [
            {"language": "en", "region": "GB"},
            {"language": "en", "region": "US"},
            {"language": "zh", "region": "CN"},
            {"language": "ja", "region": "JP"},
            {"language": "ko", "region": "KR"},
            {"language": "fr", "region": "FR"},
        ],
        "tone_profile": (
            "Understated British elegance with a modern edge. Reference heritage "
            "and the spirit of outdoor exploration. Language should be clear, "
            "confident, and quietly luxurious — never ostentatious. Emphasise "
            "functional beauty and artisanal outerwear traditions. Evoke the "
            "English countryside and London's creative energy in equal measure. "
            "Descriptions should feel grounded, tactile, and purposeful."
        ),
    },
]
"""
Brand definitions keyed by tenant ID.

Each entry contains all configuration required to initialise a Brand entity
and configure AI enrichment pipelines for that brand.
"""
