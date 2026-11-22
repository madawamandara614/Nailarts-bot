#!/usr/bin/env python3
"""
Nail Art Pinterest Auto-Publisher Bot (100% Free Stack)
-------------------------------------------------------
- Prompt & Pinterest SEO: Cloudflare Workers AI (Llama 3.1 8B) + Dynamic Combinatorial
  Nail Art Generator (thousands of unique colors, shapes, finishes, motifs, titles,
  descriptions, and hashtags — never repeats the same template!)
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
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image, ImageEnhance

BUFFER_GRAPHQL_URL = "https://api.buffer.com"
CLOUDFLARE_FLUX_MODEL = "@cf/black-forest-labs/flux-1-schnell"
CLOUDFLARE_TEXT_MODEL = "@cf/meta/llama-3.1-8b-instruct"

# ---------------------------------------------------------------------------
# Dynamic Combinatorial Nail Art Pools (100,000+ unique combinations)
# ---------------------------------------------------------------------------
NAIL_SHAPES: list[tuple[str, str]] = [
    ("long coffin", "CoffinNails"),
    ("medium almond", "AlmondNails"),
    ("short squoval", "ShortNails"),
    ("tapered ballerina", "BallerinaNails"),
    ("sleek stiletto", "StilettoNails"),
    ("soft square", "SquareNails"),
    ("Russian almond", "LuxuryNails"),
    ("short rounded", "NaturalNails"),
    ("long oval", "OvalNails"),
]

COLOR_PALETTES: list[tuple[str, str, list[str]]] = [
    ("deep crimson & milky blush", "Crimson & Blush", ["RedNails", "BurgundyNails"]),
    ("emerald green & 24k gold", "Emerald & Gold", ["EmeraldNails", "GreenNails"]),
    ("iridescent pearl & sheer champagne", "Champagne Pearl", ["PearlNails", "NeutralNails"]),
    ("sakura baby pink & milky white", "Sakura Pink", ["PinkNails", "SakuraNails"]),
    ("cobalt sapphire & liquid silver", "Sapphire & Silver", ["BlueNails", "SilverNails"]),
    ("creamy matcha latte & oat beige", "Matcha & Oat", ["MatchaNails", "SageNails"]),
    ("sunset coral & warm peach glaze", "Sunset Coral", ["CoralNails", "PeachNails"]),
    ("espresso mocha & caramel amber", "Espresso & Amber", ["BrownNails", "MochaNails"]),
    ("pastel lavender & lilac mist", "Lavender Mist", ["LavenderNails", "PurpleNails"]),
    ("black cherry & sheer rose nude", "Black Cherry", ["BlackCherryNails", "DarkNails"]),
    ("icy baby blue & frosted chrome", "Frosted Ice Blue", ["IceBlueNails", "WinterNails"]),
    ("ruby wine & velvet rose", "Ruby Velvet", ["WineNails", "VelvetNails"]),
    ("butter yellow & ivory cream", "Butter Yellow", ["YellowNails", "PastelNails"]),
    ("terracotta clay & warm bronze", "Terracotta Bronze", ["TerracottaNails", "AutumnNails"]),
    ("obsidian black & champagne gold", "Obsidian & Gold", ["BlackNails", "EdgyNails"]),
    ("rose quartz pink & rose gold", "Rose Quartz", ["RoseQuartzNails", "WeddingNails"]),
    ("pistachio cream & mint glaze", "Pistachio Mint", ["MintNails", "SpringNails"]),
    ("plum berry & iridescent violet", "Plum Berry", ["PlumNails", "BerryNails"]),
    ("holographic opal & sheer milk", "Opal Shimmer", ["OpalNails", "GlazedNails"]),
    ("cranberry syrup & frosted white", "Cranberry Syrup", ["SyrupNails", "JellyNails"]),
]

TECHNIQUES: list[tuple[str, str, str]] = [
    ("magnetic velvet cat-eye gel", "Velvet Cat-Eye", "CatEyeNails"),
    ("airbrushed aura ombre gradient", "Aura Ombre", "AuraNails"),
    ("mirror glazed pearl chrome", "Glazed Chrome", "ChromeNails"),
    ("translucent Korean syrup jelly", "Syrup Jelly", "KoreanNails"),
    ("ultra-thin micro French tips", "Micro French", "FrenchTipNails"),
    ("encapsulated crystal marble", "Crystal Marble", "MarbleNails"),
    ("glossy tortoiseshell jelly", "Tortoiseshell", "TortoiseshellNails"),
    ("blooming watercolor ink", "Watercolor Bloom", "WatercolorNails"),
    ("sculpted 3D molten chrome waves", "3D Liquid Chrome", "3DNailArt"),
    ("glass-like sheer builder gel", "Glass Gel", "GlassNails"),
    ("crushed mother-of-pearl inlay", "Shell Inlay", "ShellNails"),
    ("matte velvet with glossy drip tips", "Matte & Gloss", "MatteNails"),
]

ACCENT_MOTIFS: list[tuple[str, str, str]] = [
    ("delicate hand-painted monarch butterflies", "Butterfly", "ButterflyNails"),
    ("sculpted 3D translucent glass flower petals", "3D Floral", "3DFlowerNails"),
    ("tiny 3D satin coquette ribbons and micro pearls", "Coquette Bow", "CoquetteNails"),
    ("raised metallic celestial starbursts and crescent moons", "Celestial", "CelestialNails"),
    ("fine botanical branches with micro crystal dewdrops", "Botanical", "FloralNails"),
    ("delicate 24k gold leaf foil flakes", "Gold Foil", "GoldFoilNails"),
    ("minimalist swirling abstract ribbons", "Abstract Swirl", "SwirlNails"),
    ("dainty micro-rhinestone clusters near the cuticle", "Crystal", "RhinestoneNails"),
    ("sculpted 3D clear water droplets", "Water Droplet", "WaterDropNails"),
    ("dainty hand-painted cherries and tiny hearts", "Cherry Heart", "CuteNails"),
    ("delicate white lace filigree detailing", "Lace", "BridalNails"),
    ("clean minimalist negative-space line art", "Minimalist", "MinimalistNails"),
]

OCCASIONS: list[tuple[str, str]] = [
    ("everyday clean-girl elegance", "CleanGirlNails"),
    ("bridal and wedding guest glam", "WeddingNailInspo"),
    ("romantic date-night vibes", "DateNightNails"),
    ("effortless vacation and brunch style", "SummerNails"),
    ("cozy autumn and winter luxury", "FallNailIdeas"),
    ("fresh spring salon inspiration", "SpringNailInspo"),
    ("party-ready evening sparkle", "PartyNails"),
    ("chic minimalist office wear", "ClassyNails"),
]

TITLE_PATTERNS: list[str] = [
    "{color_short} {tech_short} {motif_short} Nails | {shape_cap} Inspo",
    "Stunning {color_short} {motif_short} Nail Art ({tech_short} Look)",
    "{tech_short} {color_short} Nails with {motif_short} Details",
    "Trending {color_short} {shape_cap} Nails — {tech_short} Ideas",
    "Save For Your Next Manicure: {color_short} {motif_short} Nails",
    "Obsessed With These {color_short} {tech_short} {shape_cap} Nails",
    "Chic {color_short} Nail Design | {tech_short} & {motif_short}",
    "Dreamy {color_short} {motif_short} Nails to Try Next",
]

DESCRIPTION_TEMPLATES: list[str] = [
    "Show this {color} manicure to your nail tech! These {shape} nails blend {tech} with {motif} for {occasion}.",
    "Looking for a fresh manicure refresh? This {color} {tech} set on {shape} nails features {motif} — pure perfection for {occasion}.",
    "Pinned straight to the dream salon board: glossy {shape} nails in {color} with {tech} and {motif}, made for {occasion}.",
    "Can't stop staring at the shine on these {color} {shape} nails. The {tech} finish paired with {motif} elevates {occasion}.",
    "Instant manicure envy! {shape_cap} nails styled in {color} using {tech} and finished with {motif} for {occasion}.",
    "Upgrade your nail game with this {color} look — {tech} meets {motif} on sleek {shape} nails, ideal for {occasion}.",
    "Soft lighting, glass-like shine, and {color} tones. These {shape} {tech} nails with {motif} are a must-save for {occasion}.",
    "Need your next nail appointment idea? Try {color} {tech} on {shape} nails accented with {motif} for {occasion}.",
]

EXTRA_GENERAL_TAGS: list[str] = [
    "NailArt", "NailInspo", "NailIdeas", "NailDesign", "GelNails",
    "GelManicure", "PinterestNails", "AestheticNails", "ManicureIdeas",
    "SalonNails", "TrendyNails", "NailsOfTheDay", "NailTrends2026",
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


def _load_recent_themes(history_path: Path) -> list[str]:
    if not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data[-25:]]
    except Exception:
        pass
    return []


def _save_recent_theme(history_path: Path, palette_short: str, motif_short: str) -> None:
    try:
        recent = _load_recent_themes(history_path)
        recent.append(f"{palette_short}|{motif_short}")
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(recent[-30:], indent=2), encoding="utf-8")
    except Exception:
        pass


def _pick_unique_combo(history_path: Path) -> dict[str, Any]:
    recent = set(_load_recent_themes(history_path))
    recent_colors = {item.split("|")[0] for item in recent if "|" in item}

    fresh_palettes = [p for p in COLOR_PALETTES if p[1] not in recent_colors]
    palette = random.choice(fresh_palettes or COLOR_PALETTES)
    shape = random.choice(NAIL_SHAPES)
    tech = random.choice(TECHNIQUES)
    motif = random.choice(ACCENT_MOTIFS)
    occasion = random.choice(OCCASIONS)

    tag_pool = list(palette[2]) + [shape[1], tech[2], motif[2], occasion[1]]
    tag_pool.extend(random.sample(EXTRA_GENERAL_TAGS, k=3))
    seen: set[str] = set()
    unique_tags: list[str] = []
    for t in tag_pool:
        clean = re.sub(r"[^A-Za-z0-9]", "", t)
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            unique_tags.append(f"#{clean}")
        if len(unique_tags) >= 8:
            break

    return {
        "shape": shape[0],
        "shape_cap": shape[0].title(),
        "color": palette[0],
        "color_short": palette[1],
        "tech": tech[0],
        "tech_short": tech[1],
        "motif": motif[0],
        "motif_short": motif[1],
        "occasion": occasion[0],
        "hashtags": " ".join(unique_tags),
    }


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """Robustly extract a JSON object from LLM output even if wrapped in prose or fences."""
    cleaned = raw_text.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = cleaned[start : end + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        fixed = re.sub(r"(?<!\\)\n", " ", candidate)
        try:
            parsed = json.loads(fixed)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def build_pin_content(
    cf_account_id: str | None = None,
    cf_api_token: str | None = None,
    use_ai_prompt: bool = True,
    history_path: Path = Path("generated_pins/history.json"),
) -> PinContent:
    """
    Generate a 100% unique Nail Art design, image prompt, Pinterest SEO title,
    natural varied description, and tailored hashtags for every single run.
    """
    combo = _pick_unique_combo(history_path)
    theme = f"{combo['color_short']} {combo['tech_short']} {combo['motif_short']} Nails"

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
                "You are a viral Pinterest Nail Art creative director and SEO copywriter. "
                "Output ONLY a single-line valid JSON object with keys: "
                "title, description, image_prompt, alt_text. No markdown, no extra commentary. "
                "Requirements: "
                "1) title: catchy, natural Pinterest title (<= 85 chars), vary style every time. "
                "2) description: fresh, engaging 2-sentence Pinterest caption tailored to this exact "
                "design followed by 7-8 unique niche hashtags (<= 380 chars). NEVER use generic "
                "cliches like 'Save this gorgeous look for your next salon appointment'. "
                "3) image_prompt: ultra-detailed photorealistic macro nail photography prompt of "
                "manicured fingers in a vertical 2:3 portrait close-up, studio softbox reflections, "
                "glass-like gel topcoat, warm natural skin tones, ending with '8k, photorealistic, no text, no watermark'. "
                "4) alt_text: concise descriptive alt text (<= 140 chars)."
            )
            user_msg = (
                f"Design brief: {combo['shape']} nails in {combo['color']} using {combo['tech']}, "
                f"decorated with {combo['motif']}, styled for {combo['occasion']}. "
                f"Write a totally fresh title, description with matching hashtags, and photorealistic image prompt."
            )
            resp = requests.post(
                url,
                headers=headers,
                json={
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.9,
                    "max_tokens": 500,
                },
                timeout=45,
            )
            resp.raise_for_status()
            raw_text = resp.json().get("result", {}).get("response", "")
            parsed = _extract_json_object(raw_text)
            if parsed:
                title = str(parsed.get("title", "")).strip()[:100]
                description = str(parsed.get("description", "")).strip()[:490]
                image_prompt = str(parsed.get("image_prompt", "")).strip()
                alt_text = str(parsed.get("alt_text") or title).strip()[:200]
                if title and description and image_prompt:
                    if "#" not in description:
                        description = f"{description}\n\n{combo['hashtags']}"[:490]
                    _save_recent_theme(history_path, combo["color_short"], combo["motif_short"])
                    return PinContent(
                        theme=theme,
                        title=title,
                        description=description,
                        image_prompt=image_prompt,
                        alt_text=alt_text,
                    )
        except Exception as exc:
            print(f"[INFO] AI copywriter fallback triggered (using dynamic combinatorial generator): {exc}")

    title = random.choice(TITLE_PATTERNS).format(**combo)[:100]
    body = random.choice(DESCRIPTION_TEMPLATES).format(**combo)
    description = f"{body}\n\n{combo['hashtags']}"[:490]
    image_prompt = (
        f"Ultra-detailed macro beauty photography of {combo['shape']} nails in {combo['color']} "
        f"with {combo['tech']} finish, accented with {combo['motif']}, high-gloss glass-like gel "
        f"topcoat catching soft studio softbox reflections, vertical 2:3 portrait close-up of "
        f"manicured fingers centered cleanly, soft natural skin tones, Pinterest viral nail art "
        f"inspiration for {combo['occasion']}, 8k, photorealistic, no text, no watermark"
    )
    alt_text = f"{combo['color_short']} {combo['shape']} nails with {combo['tech_short']} and {combo['motif_short']}"[:200]

    _save_recent_theme(history_path, combo["color_short"], combo["motif_short"])
    return PinContent(
        theme=theme,
        title=title,
        description=description,
        image_prompt=image_prompt,
        alt_text=alt_text,
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
    if resp.status_code == 401:
        raise RuntimeError(
            "Cloudflare 401 Unauthorized! Check CLOUDFLARE_API_TOKEN in GitHub Secrets.\n"
            f"Server response: {resp.text}"
        )
    if not resp.ok:
        raise RuntimeError(f"Cloudflare API HTTP {resp.status_code}: {resp.text}")

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
    if not resp.ok:
        raise RuntimeError(f"Buffer API HTTP {resp.status_code}: {resp.text}")
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

    buffer_api_key = os.getenv("BUFFER_API_KEY", "").strip()
    cf_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    cf_api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    imgbb_api_key = os.getenv("IMGBB_API_KEY", "").strip()

    if args.list_channels:
        if not buffer_api_key:
            print("ERROR: BUFFER_API_KEY secret is missing in GitHub Actions!", file=sys.stderr)
            return 1
        list_channels_command(buffer_api_key)
        return 0

    meta_path = Path(args.metadata_file)

    if args.generate_only:
        if not cf_account_id or not cf_api_token:
            print("ERROR: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN secrets are missing!", file=sys.stderr)
            return 1

        use_ai_prompt = os.getenv("USE_AI_PROMPT", "true").lower() == "true"
        steps = int(os.getenv("FLUX_STEPS", "6"))
        make_vertical = os.getenv("PIN_VERTICAL_CROP", "true").lower() == "true"

        pin = build_pin_content(cf_account_id, cf_api_token, use_ai_prompt=use_ai_prompt)
        print(f"[1/2] Generated Nail Art Concept: {pin.theme}")
        print(f"      Title: {pin.title}")
        print(f"      Description: {pin.description}")

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
        print("ERROR: BUFFER_API_KEY secret is missing in GitHub Actions!", file=sys.stderr)
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
            print("ERROR: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN secrets are missing!", file=sys.stderr)
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
