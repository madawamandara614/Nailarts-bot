#!/usr/bin/env python3
"""
Nail Art Pinterest Auto-Publisher Bot (100% Free Stack)
-------------------------------------------------------
- Prompt & Pinterest SEO: Cloudflare Workers AI (Llama 3.1 8B) + rich built-in Nail Art prompt library
- Image Generation: Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell, 10,000 free neurons/day)
- Image Hosting: GitHub Raw URL (free, built-in for public repos) OR ImgBB (free API for private repos)
- Publishing: Buffer GraphQL API (https://api.buffer.com) — STRICTLY filtered to Pinterest ONLY
  (Connected Facebook Pages or other channels are always ignored.)
"""

from __future__ import annotations

import argparse
import base64
import datetime
import io
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image, ImageEnhance

# =============================================================================
# API CREDENTIALS (Uses GitHub Secrets / env vars first, falls back to below)
# WARNING: If you upload this file to GitHub with keys inside, set repo to PRIVATE!
# =============================================================================
DEFAULT_BUFFER_API_KEY = "W7OMOgz8QA3Vn1K1wD86-_JAr3fOjQGW1lVAGH_Y2bm"
DEFAULT_CLOUDFLARE_API_TOKEN = "cfut_aqheBDMfa5t3qeYvl7aR3ZtaGOVedKZHN8S0jNuF86ebc495"
DEFAULT_CLOUDFLARE_ACCOUNT_ID = "0cefb37431a90ee5d90ddf8e4189f94e"

BUFFER_GRAPHQL_URL = "https://api.buffer.com"
CLOUDFLARE_FLUX_MODEL = "@cf/black-forest-labs/flux-1-schnell"
CLOUDFLARE_TEXT_MODEL = "@cf/meta/llama-3.1-8b-instruct"

# High-reach Pinterest nail art concepts modeled on top-performing aesthetic pins
NAIL_ART_CONCEPTS: list[dict[str, str]] = [
    {
        "theme": "Dark Red Gradient Aura Butterfly Nails",
        "title": "Save This Pin | Dark Red Gradient Butterfly Nail Art Ideas",
        "prompt": (
            "Ultra-detailed macro beauty photography of long glossy coffin nails with a deep crimson "
            "and dark burgundy ombre aura gradient over sheer milky pink base, delicate hand-painted "
            "red and black monarch butterflies, fine dark red botanical branches, tiny 3D white pearl "
            "blossoms and micro crystal dewdrops, studio softbox specular shine on glass-like gel topcoat, "
            "vertical 2:3 portrait close-up of manicured fingers centered cleanly, soft warm skin tones, "
            "photorealistic Pinterest viral nail inspo, 8k, no text, no watermark"
        ),
        "hashtags": "#NailArt #RedNails #ButterflyNails #CoffinNails #NailInspo #PinterestNails #GelNails #AestheticNails",
    },
    {
        "theme": "Pearl Chrome Glazed Donut Almond Nails",
        "title": "Glazed Pearl Chrome Almond Nails | Clean Girl Nail Inspo",
        "prompt": (
            "Macro luxury nail photography of medium-length almond nails with sheer milky pink base "
            "and iridescent pearl chrome mirror glaze finish, subtle 3D sculpted water droplets and tiny "
            "champagne gold micro-pearls near the cuticle, soft diffused daylight studio glow, vertical "
            "2:3 portrait close-up of graceful manicured hand centered cleanly, ultra-glossy gel finish, "
            "photorealistic Pinterest nail inspiration, 8k, no text, no watermark"
        ),
        "hashtags": "#ChromeNails #GlazedDonutNails #AlmondNails #CleanGirlNails #NailInspo #MilkyNails #GelManicure",
    },
    {
        "theme": "Velvet Cat-Eye Burgundy & Gold Foil Nails",
        "title": "Velvet Cat-Eye Burgundy Nails with Gold Leaf Accents",
        "prompt": (
            "Ultra-sharp macro beauty shot of glossy almond nails featuring magnetic velvet cat-eye "
            "deep wine burgundy gel polish with luminous satin shimmer, delicate 24k gold leaf flakes "
            "and minimalist fine gold French tip line, dramatic soft studio lighting highlighting the "
            "3D velvet depth, vertical 2:3 portrait close-up of manicured fingers, photorealistic luxury "
            "salon nail art, 8k, no text, no watermark"
        ),
        "hashtags": "#CatEyeNails #VelvetNails #BurgundyNails #LuxuryNails #NailDesign #NailIdeas #GelNails",
    },
    {
        "theme": "Coquette Blush Pink 3D Bow & Lace French Tips",
        "title": "Coquette Pink French Tip Nails with 3D Ribbons & Pearls",
        "prompt": (
            "Macro salon beauty photography of medium coffin nails with sheer rosy jelly pink base, "
            "crisp milky white micro French tips, tiny sculpted 3D satin white bows, delicate silver "
            "chrome stars, and mini pearl accents, dreamy soft pastel studio lighting with glossy gel "
            "reflection, vertical 2:3 portrait close-up of manicured fingers centered cleanly, viral "
            "Pinterest coquette nail aesthetic, 8k, no text, no watermark"
        ),
        "hashtags": "#CoquetteNails #PinkNails #FrenchTipNails #3DNailArt #CuteNails #NailInspo #PinterestNails",
    },
    {
        "theme": "Black Cherry Ombre & 3D Floral Jelly Nails",
        "title": "Black Cherry Ombre Nails | 3D Blossom Gel Nail Art",
        "prompt": (
            "Close-up editorial macro nail photography of long tapered ballerina nails with translucent "
            "black cherry jelly gradient fading into soft nude pink, sculpted 3D translucent glass "
            "petals with tiny silver caviar beads at the center, high-gloss wet gel shine, soft studio "
            "highlights, vertical 2:3 portrait close-up of manicured hand, photorealistic Pinterest nail "
            "art, 8k, no text, no watermark"
        ),
        "hashtags": "#BlackCherryNails #OmbreNails #JellyNails #3DFlowerNails #NailArtIdeas #LongNails #GelManicure",
    },
    {
        "theme": "Midnight Navy Celestial Gold Starburst Nails",
        "title": "Midnight Blue & Gold Celestial Nail Art Ideas",
        "prompt": (
            "Macro editorial beauty photography of glossy almond nails with deep midnight navy blue "
            "cat-eye galaxy gel polish fading into sheer milky lavender at the cuticle, raised metallic "
            "gold chrome celestial starbursts, crescent moons, and tiny crystal rhinestones, ultra-glossy "
            "gel topcoat reflections, vertical 2:3 portrait close-up of manicured fingers, photorealistic "
            "Pinterest viral nails, 8k, no text, no watermark"
        ),
        "hashtags": "#CelestialNails #BlueNails #GoldChromeNails #AlmondNails #NailInspo #AestheticNails #GelNails",
    },
    {
        "theme": "Matcha Latte Swirl & Gold Chrome Almond Nails",
        "title": "Matcha Green Swirl Nails | Aesthetic Spring Nail Inspo",
        "prompt": (
            "Macro salon nail photography of sleek medium almond nails with creamy oat-milk nude base, "
            "organic sage matcha green abstract gel swirls, delicate raised 3D molten gold chrome "
            "lines, glossy glass-like topcoat catching soft natural daylight, vertical 2:3 portrait "
            "close-up of manicured hand centered cleanly, viral Pinterest nail art inspiration, 8k, "
            "no text, no watermark"
        ),
        "hashtags": "#MatchaNails #GreenNails #SwirlNails #SpringNails #AlmondNails #NailInspo #GelNails",
    },
    {
        "theme": "Rose Quartz Marble & Rose Gold Foil Nails",
        "title": "Rose Quartz Crystal Marble Nails | Elegant Nail Ideas",
        "prompt": (
            "Ultra-detailed macro beauty shot of glossy coffin nails styled like translucent pink rose "
            "quartz crystal marble with delicate milky white veining and subtle rose-gold foil flakes "
            "encapsulated in clear builder gel, high-shine specular highlights, vertical 2:3 portrait "
            "close-up of manicured fingers, photorealistic Pinterest wedding and luxury nail inspo, 8k, "
            "no text, no watermark"
        ),
        "hashtags": "#RoseQuartzNails #MarbleNails #PinkNails #WeddingNails #ElegantNails #NailInspo #GelNails",
    },
    {
        "theme": "Espresso Brown Tortoiseshell & Gold French Nails",
        "title": "Chic Tortoiseshell & Espresso French Tip Nail Art",
        "prompt": (
            "Macro luxury nail photography of glossy medium almond nails combining translucent amber "
            "and dark espresso brown tortoiseshell jelly patterns with sleek chocolate French tips and "
            "thin metallic gold chrome borders, rich studio lighting with crisp glass gel shine, "
            "vertical 2:3 portrait close-up of manicured hand, viral Pinterest autumn nail inspo, 8k, "
            "no text, no watermark"
        ),
        "hashtags": "#TortoiseshellNails #BrownNails #FallNails #FrenchTips #NailArt #NailInspo #ClassyNails",
    },
    {
        "theme": "Lavender Aura Chrome Butterfly Nails",
        "title": "Dreamy Lavender Aura Nails with Silver Chrome Butterflies",
        "prompt": (
            "Macro beauty photography of long glossy almond nails with soft sheer milky base and "
            "glowing pastel lavender-lilac airbrushed aura centers, delicate 3D liquid silver chrome "
            "butterflies and tiny micro-rhinestones, luminous studio lighting, vertical 2:3 portrait "
            "close-up of manicured fingers centered cleanly, photorealistic Pinterest nail inspo, 8k, "
            "no text, no watermark"
        ),
        "hashtags": "#AuraNails #LavenderNails #PurpleNails #ButterflyNails #ChromeNails #NailInspo #PinterestNails",
    },
]


@dataclass
class PinContent:
    theme: str
    title: str
    description: str
    image_prompt: str
    alt_text: str


@dataclass
class PinterestTarget:
    organization_id: str
    channel_id: str
    channel_name: str
    board_service_id: str
    board_name: str


def build_pin_content(
    cf_account_id: str | None = None,
    cf_api_token: str | None = None,
    use_ai_prompt: bool = True,
) -> PinContent:
    """
    Generate a fresh Nail Art image prompt and Pinterest SEO title/description.
    Uses Cloudflare Workers AI (Llama 3.1 8B) when enabled, with automatic fallback
    to the curated high-reach Nail Art concept library.
    """
    base = random.choice(NAIL_ART_CONCEPTS)

    if use_ai_prompt and cf_account_id and cf_api_token:
        try:
            url = (
                f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}"
                f"/ai/run/{CLOUDFLARE_TEXT_MODEL}"
            )
            headers = {
                "Authorization": f"Bearer {cf_api_token}",
                "Content-Type": "application/json",
            }
            system_msg = (
                "You are a viral Pinterest Nail Art creative director and SEO specialist. "
                "Return ONLY valid JSON with keys: theme, title, description, image_prompt, alt_text. "
                "Rules: title <= 90 chars, catchy Pinterest save-worthy wording; "
                "description <= 350 chars with 6-8 relevant nail art hashtags; "
                "image_prompt must describe photorealistic macro nail photography of manicured fingers "
                "in a vertical 2:3 portrait close-up with ultra-glossy gel finish, studio lighting, "
                "and end with '8k, photorealistic, no text, no watermark'."
            )
            user_msg = (
                f"Create a fresh, unique viral Pinterest nail art design inspired by the style of "
                f"'{base['theme']}' (vary colors, textures, or accents so every pin feels new)."
            )
            resp = requests.post(
                url,
                headers=headers,
                json={
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    "max_tokens": 450,
                },
                timeout=45,
            )
            resp.raise_for_status()
            raw_text = resp.json().get("result", {}).get("response", "").strip()
            if "```" in raw_text:
                start = raw_text.find("{")
                end = raw_text.rfind("}")
                if start != -1 and end != -1:
                    raw_text = raw_text[start : end + 1]
            parsed = json.loads(raw_text)
            title = str(parsed["title"]).strip()[:100]
            description = str(parsed["description"]).strip()[:490]
            image_prompt = str(parsed["image_prompt"]).strip()
            alt_text = str(parsed.get("alt_text") or title).strip()[:200]
            theme = str(parsed.get("theme") or base["theme"]).strip()
            if title and description and image_prompt:
                return PinContent(
                    theme=theme,
                    title=title,
                    description=description,
                    image_prompt=image_prompt,
                    alt_text=alt_text,
                )
        except Exception as exc:
            print(f"[INFO] AI prompt expansion fallback triggered: {exc}")

    description = (
        f"Save this gorgeous {base['theme']} look for your next salon appointment! "
        f"Ultra-glossy aesthetic nail art inspiration perfect for everyday glam or special occasions.\n\n"
        f"{base['hashtags']}"
    )
    return PinContent(
        theme=base["theme"],
        title=base["title"][:100],
        description=description[:490],
        image_prompt=base["prompt"],
        alt_text=f"{base['theme']} manicured nail art inspiration",
    )


def format_for_pinterest(image_bytes: bytes, output_path: Path, make_vertical: bool = True) -> Path:
    """
    Convert raw AI image bytes into a crisp Pinterest-optimized JPEG.
    If make_vertical=True, center-crops to 2:3 aspect ratio and resizes to 1000x1500
    (Pinterest's recommended high-reach vertical Pin dimensions).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        if make_vertical:
            w, h = img.size
            target_ratio = 2 / 3
            current_ratio = w / h
            if current_ratio > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            elif current_ratio < target_ratio:
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))
            img = img.resize((1000, 1500), Image.Resampling.LANCZOS)

        img = ImageEnhance.Contrast(img).enhance(1.05)
        img = ImageEnhance.Sharpness(img).enhance(1.08)
        img.save(output_path, format="JPEG", quality=92, optimize=True)
    return output_path


def generate_image_cloudflare(
    prompt: str,
    account_id: str,
    api_token: str,
    steps: int = 6,
) -> bytes:
    """
    Generate a high-resolution image using Cloudflare Workers AI FLUX.1-schnell
    (Free tier: 10,000 Neurons/day, ~170 images/day).
    """
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/ai/run/{CLOUDFLARE_FLUX_MODEL}"
    )
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "steps": max(1, min(8, steps)),
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("success", True):
        raise RuntimeError(f"Cloudflare Workers AI error: {data.get('errors')}")

    image_b64 = data.get("result", {}).get("image")
    if not image_b64:
        raise RuntimeError(f"Cloudflare response missing result.image: {data}")
    return base64.b64decode(image_b64)


def upload_image_imgbb(image_path: Path, imgbb_api_key: str) -> str:
    """Upload JPEG to ImgBB (free permanent hosting, ideal for private GitHub repos)."""
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": imgbb_api_key, "image": image_b64},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"ImgBB upload failed: {data}")
    return str(data["data"]["url"])


def build_github_raw_url(repo: str, branch: str, relative_path: Path) -> str:
    """Build a permanent public raw.githubusercontent.com URL for a committed image."""
    rel_posix = quote(relative_path.as_posix())
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{rel_posix}"


def buffer_graphql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query or mutation against https://api.buffer.com."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = requests.post(BUFFER_GRAPHQL_URL, headers=headers, json=payload, timeout=45)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"Buffer GraphQL errors: {body['errors']}")
    return body.get("data", {})


def resolve_pinterest_target(
    api_key: str,
    preferred_channel_id: str | None = None,
    preferred_board_name: str | None = None,
    preferred_board_service_id: str | None = None,
) -> PinterestTarget:
    """
    Fetch Buffer channels and STRICTLY select ONLY a Pinterest channel.
    Facebook Pages, Instagram, and all other services are explicitly ignored.
    """
    org_query = """
    query GetOrganizations {
      account {
        organizations {
          id
          name
        }
      }
    }
    """
    org_data = buffer_graphql(api_key, org_query)
    orgs = org_data.get("account", {}).get("organizations", [])
    if not orgs:
        raise RuntimeError("No Buffer organizations found for this API key.")

    channels_query = """
    query GetChannels($organizationId: OrganizationId!) {
      channels(input: { organizationId: $organizationId, filter: { isLocked: false } }) {
        id
        name
        displayName
        service
        isDisconnected
        metadata {
          ... on PinterestMetadata {
            boards {
              id
              name
              serviceId
            }
          }
        }
      }
    }
    """

    pinterest_candidates: list[tuple[str, dict[str, Any]]] = []

    for org in orgs:
        org_id = org["id"]
        ch_data = buffer_graphql(api_key, channels_query, {"organizationId": org_id})
        for ch in ch_data.get("channels", []):
            service = str(ch.get("service", "")).lower()
            ch_label = ch.get("displayName") or ch.get("name") or ch.get("id")
            if service != "pinterest":
                print(f"[SKIP] Ignoring non-Pinterest channel: {ch_label} (service={service})")
                continue
            if ch.get("isDisconnected"):
                print(f"[WARN] Skipping disconnected Pinterest channel: {ch_label}")
                continue
            pinterest_candidates.append((org_id, ch))

    if not pinterest_candidates:
        raise RuntimeError(
            "No active Pinterest channel found in Buffer. "
            "Connect your Pinterest Business account in Buffer first."
        )

    selected_org_id, selected_ch = pinterest_candidates[0]
    if preferred_channel_id:
        matched = [item for item in pinterest_candidates if item[1]["id"] == preferred_channel_id]
        if not matched:
            available = [f"{c['id']} ({c.get('displayName') or c.get('name')})" for _, c in pinterest_candidates]
            raise RuntimeError(
                f"BUFFER_PINTEREST_CHANNEL_ID='{preferred_channel_id}' not found among Pinterest channels: {available}"
            )
        selected_org_id, selected_ch = matched[0]

    if str(selected_ch.get("service", "")).lower() != "pinterest":
        raise RuntimeError("Safety check failed: target channel is not Pinterest!")

    boards = (selected_ch.get("metadata") or {}).get("boards") or []
    if not boards and not preferred_board_service_id:
        raise RuntimeError(
            "No Pinterest boards found on this Buffer channel. "
            "Create at least one board on Pinterest and refresh your Buffer channel."
        )

    board_service_id = preferred_board_service_id or ""
    board_name = "Custom Board"

    if not board_service_id:
        chosen_board = boards[0]
        if preferred_board_name:
            needle = preferred_board_name.strip().lower()
            exact = [b for b in boards if str(b.get("name", "")).strip().lower() == needle]
            partial = [b for b in boards if needle in str(b.get("name", "")).strip().lower()]
            if exact:
                chosen_board = exact[0]
            elif partial:
                chosen_board = partial[0]
            else:
                names = [b.get("name") for b in boards]
                raise RuntimeError(
                    f"Pinterest board '{preferred_board_name}' not found. Available boards: {names}"
                )
        board_service_id = str(chosen_board["serviceId"])
        board_name = str(chosen_board.get("name") or board_service_id)

    return PinterestTarget(
        organization_id=selected_org_id,
        channel_id=str(selected_ch["id"]),
        channel_name=str(selected_ch.get("displayName") or selected_ch.get("name") or selected_ch["id"]),
        board_service_id=board_service_id,
        board_name=board_name,
    )


def publish_pin_to_buffer(
    api_key: str,
    target: PinterestTarget,
    pin: PinContent,
    image_url: str,
    mode: str = "shareNow",
    destination_url: str | None = None,
) -> dict[str, Any]:
    """
    Publish or queue a Pin to ONLY the resolved Pinterest channel via Buffer GraphQL createPost.
    """
    if mode not in {"shareNow", "addToQueue", "shareNext"}:
        raise ValueError(f"Unsupported BUFFER_POST_MODE '{mode}'. Use shareNow, addToQueue, or shareNext.")

    pinterest_meta: dict[str, Any] = {
        "boardServiceId": target.board_service_id,
        "title": pin.title,
    }
    if destination_url:
        pinterest_meta["url"] = destination_url

    mutation = """
    mutation CreatePinterestPost($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess {
          post {
            id
            status
            dueAt
            text
            channelId
            channelService
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    variables = {
        "input": {
            "channelId": target.channel_id,
            "text": pin.description,
            "schedulingType": "automatic",
            "mode": mode,
            "assets": [
                {
                    "image": {
                        "url": image_url,
                        "metadata": {
                            "altText": pin.alt_text,
                        },
                    }
                }
            ],
            "metadata": {
                "pinterest": pinterest_meta,
            },
        }
    }

    data = buffer_graphql(api_key, mutation, variables)
    result = data.get("createPost", {})
    typename = result.get("__typename")
    if typename != "PostActionSuccess":
        raise RuntimeError(f"Buffer createPost failed ({typename}): {result.get('message', result)}")
    return result["post"]


def list_channels_command(api_key: str) -> None:
    """Print all Buffer channels and Pinterest boards without posting anything."""
    org_data = buffer_graphql(
        api_key,
        "query { account { organizations { id name } } }",
    )
    for org in org_data.get("account", {}).get("organizations", []):
        print(f"\nOrganization: {org['name']} (id={org['id']})")
        ch_data = buffer_graphql(
            api_key,
            """
            query($organizationId: OrganizationId!) {
              channels(input: { organizationId: $organizationId }) {
                id name displayName service isDisconnected isLocked
                metadata { ... on PinterestMetadata { boards { id name serviceId } } }
              }
            }
            """,
            {"organizationId": org["id"]},
        )
        for ch in ch_data.get("channels", []):
            service = str(ch.get("service", "")).lower()
            tag = "TARGET (Pinterest)" if service == "pinterest" else "IGNORED"
            print(f"  - [{tag}] {ch.get('displayName') or ch.get('name')} | service={service} | channelId={ch['id']}")
            boards = (ch.get("metadata") or {}).get("boards") or []
            for b in boards:
                print(f"      * Board: {b['name']} | boardServiceId={b['serviceId']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nail Art Pinterest Auto-Publisher Bot (Buffer + Cloudflare AI)")
    parser.add_argument("--list-channels", action="store_true", help="List Buffer channels and Pinterest boards, then exit.")
    parser.add_argument("--generate-only", action="store_true", help="Generate and save the nail art image + metadata JSON only.")
    parser.add_argument("--publish-image-url", type=str, help="Skip image generation and publish an already-hosted image URL.")
    parser.add_argument("--metadata-file", type=str, default="generated_pins/latest_pin.json", help="Path for saved pin metadata.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    buffer_api_key = (os.getenv("BUFFER_API_KEY") or DEFAULT_BUFFER_API_KEY).strip()
    cf_account_id = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or DEFAULT_CLOUDFLARE_ACCOUNT_ID).strip()
    cf_api_token = (os.getenv("CLOUDFLARE_API_TOKEN") or DEFAULT_CLOUDFLARE_API_TOKEN).strip()
    imgbb_api_key = os.getenv("IMGBB_API_KEY", "").strip()

    if args.list_channels:
        if not buffer_api_key:
            print("ERROR: BUFFER_API_KEY is required for --list-channels.", file=sys.stderr)
            return 1
        list_channels_command(buffer_api_key)
        return 0

    meta_path = Path(args.metadata_file)

    if args.generate_only:
        if not cf_account_id or not cf_api_token:
            print("ERROR: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required.", file=sys.stderr)
            return 1

        use_ai_prompt = os.getenv("USE_AI_PROMPT", "true").lower() == "true"
        steps = int(os.getenv("FLUX_STEPS", "6"))
        make_vertical = os.getenv("PIN_VERTICAL_CROP", "true").lower() == "true"

        pin = build_pin_content(cf_account_id, cf_api_token, use_ai_prompt=use_ai_prompt)
        print(f"[1/2] Generated Nail Art Concept: {pin.theme}")
        print(f"      Title: {pin.title}")

        raw_bytes = generate_image_cloudflare(pin.image_prompt, cf_account_id, cf_api_token, steps=steps)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        img_rel_path = Path("generated_pins") / f"nail_art_{timestamp}.jpg"
        format_for_pinterest(raw_bytes, img_rel_path, make_vertical=make_vertical)
        print(f"[2/2] Saved Pinterest-ready 1000x1500 image to: {img_rel_path}")

        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(
                {
                    "theme": pin.theme,
                    "title": pin.title,
                    "description": pin.description,
                    "image_prompt": pin.image_prompt,
                    "alt_text": pin.alt_text,
                    "image_path": img_rel_path.as_posix(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 0

    if not buffer_api_key:
        print("ERROR: BUFFER_API_KEY is required.", file=sys.stderr)
        return 1

    if args.publish_image_url:
        if not meta_path.exists():
            print(f"ERROR: Metadata file not found: {meta_path}", file=sys.stderr)
            return 1
        saved = json.loads(meta_path.read_text(encoding="utf-8"))
        pin = PinContent(
            theme=saved["theme"],
            title=saved["title"],
            description=saved["description"],
            image_prompt=saved["image_prompt"],
            alt_text=saved["alt_text"],
        )
        image_url = args.publish_image_url
    else:
        if not cf_account_id or not cf_api_token:
            print("ERROR: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required.", file=sys.stderr)
            return 1
        if not imgbb_api_key:
            print("ERROR: IMGBB_API_KEY is required for one-shot mode without --publish-image-url.", file=sys.stderr)
            return 1

        pin = build_pin_content(cf_account_id, cf_api_token, use_ai_prompt=True)
        raw_bytes = generate_image_cloudflare(pin.image_prompt, cf_account_id, cf_api_token)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        img_path = format_for_pinterest(raw_bytes, Path("generated_pins") / f"nail_art_{timestamp}.jpg")
        image_url = upload_image_imgbb(img_path, imgbb_api_key)

    target = resolve_pinterest_target(
        api_key=buffer_api_key,
        preferred_channel_id=os.getenv("BUFFER_PINTEREST_CHANNEL_ID", "").strip() or None,
        preferred_board_name=os.getenv("PINTEREST_BOARD_NAME", "").strip() or None,
        preferred_board_service_id=os.getenv("PINTEREST_BOARD_SERVICE_ID", "").strip() or None,
    )
    print(f"[BUFFER] Target locked to Pinterest ONLY -> Channel: {target.channel_name} ({target.channel_id}) | Board: {target.board_name}")

    post_mode = os.getenv("BUFFER_POST_MODE", "shareNow").strip() or "shareNow"
    dest_url = os.getenv("PIN_DESTINATION_URL", "").strip() or None

    post = publish_pin_to_buffer(
        api_key=buffer_api_key,
        target=target,
        pin=pin,
        image_url=image_url,
        mode=post_mode,
        destination_url=dest_url,
    )
    print(f"[SUCCESS] Published to Pinterest via Buffer! Post ID: {post['id']} | Status: {post['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
