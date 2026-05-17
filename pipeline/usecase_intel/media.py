"""Article-scoped visual asset discovery and materialization."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

try:  # Optional at import time; requirements.txt pins it for normal use.
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised only in minimal envs
    BeautifulSoup = None  # type: ignore[assignment]

from .clean import (
    NOISE_HINT_RE,
    _attrs_text,
    _best_content_root,
    _decode_bytes,
    _is_noise_tag,
    looks_like_html,
)

IMAGE_SOURCE_ATTRS = (
    "src",
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-url",
    "data-image",
)
IMAGE_EXTENSIONS = {".avif", ".gif", ".jpg", ".jpeg", ".png", ".svg", ".webp"}
IMAGE_NOISE_RE = re.compile(
    r"\b(logo|favicon|icon|sprite|avatar|profile|headshot|tracking|pixel|"
    r"spacer|loader|placeholder|badge|social|share|advertisement|ad-|ads-)\b",
    re.IGNORECASE,
)
DIAGRAM_IMAGE_HINT_RE = re.compile(
    r"\b(architecture|architectural|diagram|workflow|flow|data[-_\s]?flow|"
    r"pipeline|topology|reference[-_\s]?architecture|solution[-_\s]?overview|"
    r"system[-_\s]?overview|components?|integration|deployment)\b",
    re.IGNORECASE,
)
META_IMAGE_NAMES = {
    "og:image",
    "og:image:url",
    "og:image:secure_url",
    "twitter:image",
    "twitter:image:src",
}
IMAGE_SUFFIX_BY_CONTENT_TYPE = {
    "image/avif": ".avif",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}
CONTENT_TYPE_BY_IMAGE_SUFFIX = {
    suffix: content_type
    for content_type, suffix in IMAGE_SUFFIX_BY_CONTENT_TYPE.items()
    if content_type != "image/jpg"
}
SOURCE_DIVERSE_MIN_SCORE = 2
IMAGE_SIGNATURE_SUFFIXES = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
)


def _inline_text(value: object, *, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _dimension(value: object) -> Optional[int]:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _srcset_urls(value: object) -> list[str]:
    ranked: list[tuple[float, str]] = []
    for index, raw_part in enumerate(str(value or "").split(",")):
        part = raw_part.strip()
        if not part:
            continue
        bits = part.split()
        raw_url = bits[0].strip()
        descriptor = bits[1].strip() if len(bits) > 1 else ""
        rank = float(index)
        match = re.match(r"(\d+(?:\.\d+)?)(w|x)?$", descriptor)
        if match:
            rank = float(match.group(1))
            if match.group(2) == "x":
                rank *= 1000.0
        ranked.append((rank, raw_url))
    return [url for _rank, url in sorted(ranked, key=lambda item: item[0], reverse=True)]


def _absolute_image_url(raw_url: object, base_url: str) -> Optional[str]:
    value = str(raw_url or "").strip()
    if not value or value.startswith("#"):
        return None
    if value.lower().startswith(("data:", "blob:", "javascript:", "mailto:", "tel:")):
        return None
    resolved = urljoin(base_url, value) if base_url else value
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"}:
        return None
    return resolved


def _append_image_urls(node: object, raw_urls: list[str]) -> None:
    get = getattr(node, "get", None)
    if get is None:
        return
    for attr in ("srcset", "data-srcset"):
        raw_urls.extend(_srcset_urls(get(attr)))
    for attr in IMAGE_SOURCE_ATTRS:
        value = get(attr)
        if value:
            raw_urls.append(str(value))


def _image_urls(tag: object, base_url: str) -> list[str]:
    raw_urls: list[str] = []
    find_parent = getattr(tag, "find_parent", None)
    picture = find_parent("picture") if find_parent else None
    if picture is not None:
        for source in picture.find_all("source"):
            _append_image_urls(source, raw_urls)
    _append_image_urls(tag, raw_urls)

    urls: list[str] = []
    seen: set[str] = set()
    for raw_url in raw_urls:
        absolute = _absolute_image_url(raw_url, base_url)
        if absolute and absolute not in seen:
            urls.append(absolute)
            seen.add(absolute)
    return urls


def _image_caption(tag: object) -> str:
    find_parent = getattr(tag, "find_parent", None)
    figure = find_parent("figure") if find_parent else None
    if figure is None:
        return ""
    caption = figure.find("figcaption")
    if caption is None:
        return ""
    return _inline_text(caption.get_text(" ", strip=True))


def _image_context(tag: object, caption: str) -> str:
    find_parent = getattr(tag, "find_parent", None)
    parent = find_parent("figure") if find_parent else None
    parent = parent or getattr(tag, "parent", None)
    get_text = getattr(parent, "get_text", None)
    if get_text is None:
        return caption
    return _inline_text(get_text(" ", strip=True))


def _has_noise_ancestor(tag: object, root: object) -> bool:
    parent = getattr(tag, "parent", None)
    while parent is not None and parent is not root:
        name = getattr(parent, "name", "")
        if name in {"nav", "footer", "aside", "header", "form"}:
            return True
        if _is_noise_tag(parent):
            return True
        parent = getattr(parent, "parent", None)
    return False


def _score_image(
    *,
    tag: object,
    url: str,
    alt: str,
    caption: str,
    width: Optional[int],
    height: Optional[int],
) -> tuple[int, bool]:
    image_text = " ".join([url, alt, caption, _attrs_text(tag)])
    diagram_like = bool(DIAGRAM_IMAGE_HINT_RE.search(image_text))
    score = 3
    if alt:
        score += 3
    if caption:
        score += 5
    find_parent = getattr(tag, "find_parent", None)
    if find_parent and find_parent("figure") is not None:
        score += 4
    if diagram_like:
        score += 8
    if width and width >= 320:
        score += 2
    if height and height >= 180:
        score += 2
    if width and height and width * height >= 60000:
        score += 2
    if IMAGE_NOISE_RE.search(image_text) or NOISE_HINT_RE.search(image_text):
        score -= 10
    if (width and width <= 120) or (height and height <= 120):
        score -= 7
    return score, diagram_like


def _score_inline_svg(tag: object, caption: str, context: str) -> tuple[int, bool]:
    text = " ".join([_attrs_text(tag), caption, context])
    diagram_like = bool(DIAGRAM_IMAGE_HINT_RE.search(text))
    width = _dimension(getattr(tag, "get", lambda _name: None)("width"))
    height = _dimension(getattr(tag, "get", lambda _name: None)("height"))
    score = 2
    if context:
        score += 3
    if caption:
        score += 5
    if diagram_like:
        score += 8
    if width and width >= 320:
        score += 2
    if height and height >= 180:
        score += 2
    if IMAGE_NOISE_RE.search(text) or NOISE_HINT_RE.search(text):
        score -= 10
    if (width and width <= 120) or (height and height <= 120):
        score -= 7
    return score, diagram_like


def _metadata_image_urls(soup: object, base_url: str) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tag in soup.find_all("meta"):  # type: ignore[attr-defined]
        get = getattr(tag, "get", None)
        if get is None:
            continue
        name = str(get("property") or get("name") or "").lower()
        if name not in META_IMAGE_NAMES:
            continue
        absolute = _absolute_image_url(get("content"), base_url)
        if absolute and absolute not in seen:
            urls.append((absolute, name))
            seen.add(absolute)
    for tag in soup.find_all("link"):  # type: ignore[attr-defined]
        get = getattr(tag, "get", None)
        if get is None:
            continue
        rel_value = get("rel")
        rels = rel_value if isinstance(rel_value, list) else [rel_value]
        if "image_src" not in {str(rel).lower() for rel in rels if rel}:
            continue
        absolute = _absolute_image_url(get("href"), base_url)
        if absolute and absolute not in seen:
            urls.append((absolute, "link:image_src"))
            seen.add(absolute)
    return urls


def _background_image_urls(root: object, base_url: str) -> list[tuple[str, object]]:
    urls: list[tuple[str, object]] = []
    seen: set[str] = set()
    nodes = [root]
    find_all = getattr(root, "find_all", None)
    if find_all is not None:
        nodes.extend(find_all(True))
    for tag in nodes:
        get = getattr(tag, "get", None)
        if get is None:
            continue
        style = str(get("style") or "")
        for match in re.finditer(r"url\((['\"]?)(.*?)\1\)", style, flags=re.IGNORECASE):
            absolute = _absolute_image_url(match.group(2), base_url)
            if absolute and absolute not in seen:
                urls.append((absolute, tag))
                seen.add(absolute)
    return urls


def extract_related_images(
    body: bytes,
    *,
    content_type: str = "",
    source_url: str = "",
    max_images: int = 12,
    include_embedded: bool = False,
    include_css_backgrounds: bool = True,
) -> list[dict[str, object]]:
    """Return article-scoped visual image candidates from fetched HTML bytes."""
    if BeautifulSoup is None:
        return []
    decoded = _decode_bytes(body, content_type)
    if not looks_like_html(decoded, content_type):
        return []

    soup = BeautifulSoup(decoded, "html.parser")
    root = _best_content_root(soup)
    candidates: list[dict[str, object]] = []
    seen_urls: set[str] = set()

    for tag in root.find_all("img"):
        if _has_noise_ancestor(tag, root):
            continue
        urls = _image_urls(tag, source_url)
        if not urls:
            continue
        url = urls[0]
        if url in seen_urls:
            continue
        get = getattr(tag, "get", None)
        alt = _inline_text(get("alt") if get else "")
        caption = _image_caption(tag)
        context = _image_context(tag, caption)
        width = _dimension(get("width") if get else None)
        height = _dimension(get("height") if get else None)
        score, diagram_like = _score_image(
            tag=tag,
            url=url,
            alt=alt,
            caption=caption,
            width=width,
            height=height,
        )
        if score <= 0:
            continue

        candidate: dict[str, object] = {
            "url": url,
            "source": "html-img",
            "score": score,
            "is_diagram_like": diagram_like,
        }
        if alt:
            candidate["alt"] = alt
        if caption:
            candidate["caption"] = caption
        if context and context != caption:
            candidate["context"] = context
        if width:
            candidate["width"] = width
        if height:
            candidate["height"] = height
        if len(urls) > 1:
            candidate["alternate_urls"] = urls[1:4]
        candidates.append(candidate)
        seen_urls.add(url)

    if include_css_backgrounds:
        for url, tag in _background_image_urls(root, source_url):
            if url in seen_urls or _has_noise_ancestor(tag, root):
                continue
            caption = _image_caption(tag)
            context = _image_context(tag, caption)
            score, diagram_like = _score_image(
                tag=tag,
                url=url,
                alt="",
                caption=caption,
                width=None,
                height=None,
            )
            if not diagram_like:
                score -= 1
            if score <= 0:
                continue
            candidate = {
                "url": url,
                "source": "css-background",
                "score": score,
                "is_diagram_like": diagram_like,
                "confidence": "low" if not diagram_like else "medium",
            }
            if caption:
                candidate["caption"] = caption
            if context and context != caption:
                candidate["context"] = context
            candidates.append(candidate)
            seen_urls.add(url)

    if include_embedded:
        for tag in root.find_all("svg"):
            if _has_noise_ancestor(tag, root):
                continue
            caption = _image_caption(tag)
            context = _image_context(tag, caption)
            score, diagram_like = _score_inline_svg(tag, caption, context)
            if score <= 0:
                continue
            get = getattr(tag, "get", None)
            svg = str(tag)
            candidate = {
                "source": "inline-svg",
                "score": score,
                "is_diagram_like": diagram_like,
                "embedded_body": svg.encode("utf-8"),
            }
            if caption:
                candidate["caption"] = caption
            if context and context != caption:
                candidate["context"] = context
            width = _dimension(get("width") if get else None)
            height = _dimension(get("height") if get else None)
            if width:
                candidate["width"] = width
            if height:
                candidate["height"] = height
            candidates.append(candidate)

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for url, source in _metadata_image_urls(soup, source_url):
        if url in seen_urls:
            continue
        diagram_like = bool(DIAGRAM_IMAGE_HINT_RE.search(url))
        score = 2 + (8 if diagram_like else 0)
        if IMAGE_NOISE_RE.search(url) or NOISE_HINT_RE.search(url):
            score -= 10
        if score <= 0:
            continue
        candidate = {
            "url": url,
            "source": source,
            "score": score,
            "is_diagram_like": diagram_like,
        }
        if title:
            candidate["context"] = _inline_text(title)
        candidates.append(candidate)
        seen_urls.add(url)

    candidates.sort(
        key=lambda candidate: (
            bool(candidate.get("is_diagram_like")),
            int(candidate.get("score", 0)),
        ),
        reverse=True,
    )
    return candidates[:max_images]


def _url_image_extension(url: str) -> str:
    extension = Path(urlparse(url).path).suffix.lower()
    return extension if extension in IMAGE_EXTENSIONS else ""


def _asset_suffix(content_type: str, url: str, body: bytes) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized in IMAGE_SUFFIX_BY_CONTENT_TYPE:
        return IMAGE_SUFFIX_BY_CONTENT_TYPE[normalized]
    extension = _url_image_extension(url)
    if extension:
        return extension
    body_signature = _body_image_suffix(body)
    if body_signature:
        return body_signature
    if _looks_like_svg(body):
        return ".svg"
    return ".bin"


def _content_type_for_path(path: Path) -> str:
    return CONTENT_TYPE_BY_IMAGE_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def _looks_like_error_document(body: bytes) -> bool:
    stripped = body.lstrip()
    lowered_head = stripped[:512].lower()
    return lowered_head.startswith((
        b"<!doctype",
        b"<html",
        b"<head",
        b"<body",
        b"{",
        b"[",
    ))


def _looks_like_svg(body: bytes) -> bool:
    lowered_head = body.lstrip()[:512].lower()
    return lowered_head.startswith((b"<svg", b"<?xml")) and b"<svg" in lowered_head


def _body_image_suffix(body: bytes) -> str:
    for signature, suffix in IMAGE_SIGNATURE_SUFFIXES:
        if body.startswith(signature):
            if suffix == ".webp" and b"WEBP" not in body[:16]:
                continue
            return suffix
    if b"ftypavif" in body[:32]:
        return ".avif"
    return ""


def _looks_like_image(body: bytes, content_type: str, url: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if _looks_like_error_document(body):
        return False
    if normalized.startswith("image/"):
        return True
    stripped = body.lstrip()
    lowered_head = stripped[:512].lower()
    if _body_image_suffix(body):
        return True
    if lowered_head.startswith(b"<svg") or b"<svg" in lowered_head:
        return True
    if _url_image_extension(url) and not lowered_head.startswith((b"<!doctype", b"<html")):
        return True
    return False


def _existing_asset_path(assets_dir: Path, source_digest: str) -> Optional[Path]:
    matches = sorted(assets_dir.glob(f"{source_digest}.*"))
    return matches[0] if matches else None


def _asset_source_digest(image: dict[str, object], embedded_body: bytes | None) -> str:
    if embedded_body is not None:
        return hashlib.sha256(embedded_body).hexdigest()[:16]
    source = str(image.get("url") or image.get("source") or repr(sorted(image.items())))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _finish_local_asset(
    image: dict[str, object],
    *,
    body: bytes,
    content_type: str,
    local_path: Path,
    from_cache: bool,
    final_url: str = "",
) -> dict[str, object]:
    enriched = {key: value for key, value in image.items() if key != "embedded_body"}
    enriched["local_path"] = str(local_path)
    enriched["asset_content_type"] = content_type
    enriched["asset_sha256"] = hashlib.sha256(body).hexdigest()
    enriched["asset_bytes"] = len(body)
    enriched["asset_from_cache"] = from_cache
    if final_url:
        enriched["asset_final_url"] = final_url
    return enriched


def _clean_candidate(image: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in image.items() if key != "embedded_body"}


def _write_asset(path: Path, body: bytes) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_bytes(body)
    tmp_path.replace(path)


def _materialization_plan(images: list[dict[str, object]], max_assets: int) -> list[int]:
    if max_assets <= 0:
        return []
    plan: list[int] = []

    def add(index: int) -> None:
        if index not in plan:
            plan.append(index)

    for index, image in enumerate(images):
        if image.get("is_diagram_like"):
            add(index)

    for index in range(min(2, len(images))):
        add(index)

    for source in ("css-background", "inline-svg", "og:image", "twitter:image", "link:image_src", "html-img"):
        for index, image in enumerate(images):
            if image.get("source") == source and int(image.get("score", 0)) >= SOURCE_DIVERSE_MIN_SCORE:
                add(index)
                break

    for index in range(len(images)):
        add(index)

    return plan


def materialize_related_images(
    images: list[dict[str, object]],
    *,
    assets_dir: Path,
    client: object,
    max_assets: int = 6,
    max_bytes: int = 8_000_000,
) -> list[dict[str, object]]:
    """Download or write top related image candidates so agents can inspect them."""
    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [
            {**_clean_candidate(image), "asset_error": f"asset directory unavailable: {exc}"}
            for image in images
        ]

    materialized: list[dict[str, object]] = [_clean_candidate(image) for image in images]
    materialized_assets = 0
    plan = _materialization_plan(images, max_assets)
    fetch = getattr(client, "fetch", None)

    for index in plan:
        if materialized_assets >= max_assets:
            break
        image = images[index]
        embedded_value = image.get("embedded_body")
        embedded_body = embedded_value if isinstance(embedded_value, bytes) else None

        source_digest = _asset_source_digest(image, embedded_body)
        existing = _existing_asset_path(assets_dir, source_digest)
        if existing is not None:
            body = existing.read_bytes()
            materialized[index] = _finish_local_asset(
                image,
                body=body,
                content_type=str(image.get("asset_content_type") or _content_type_for_path(existing)),
                local_path=existing,
                from_cache=True,
            )
            materialized_assets += 1
            continue

        if embedded_body is not None:
            local_path = assets_dir / f"{source_digest}.svg"
            try:
                _write_asset(local_path, embedded_body)
            except OSError as exc:
                materialized[index] = {**_clean_candidate(image), "asset_error": f"asset write failed: {exc}"}
                continue
            materialized[index] = _finish_local_asset(
                image,
                body=embedded_body,
                content_type="image/svg+xml",
                local_path=local_path,
                from_cache=False,
            )
            materialized_assets += 1
            continue

        url = str(image.get("url") or "")
        if not url:
            continue
        if fetch is None:
            materialized[index] = {**_clean_candidate(image), "asset_error": "image fetch client has no fetch method"}
            continue

        try:
            result = fetch(url, use_cache=False)
        except Exception as exc:  # noqa: BLE001 - keep the bundle useful even when image fetch fails
            materialized[index] = {**_clean_candidate(image), "asset_error": str(exc)}
            continue

        body = result.body
        content_type = str(result.content_type or "")
        if len(body) > max_bytes:
            materialized[index] = {**_clean_candidate(image), "asset_error": f"image exceeds max_bytes={max_bytes}"}
            continue
        if not _looks_like_image(body, content_type, url):
            materialized[index] = {**_clean_candidate(image), "asset_error": f"non-image response: {content_type or 'unknown content type'}"}
            continue

        suffix = _asset_suffix(content_type, url, body)
        if suffix == ".bin" and content_type.split(";", 1)[0].strip().lower().startswith("image/"):
            materialized[index] = {**_clean_candidate(image), "asset_error": f"unknown image type: {content_type}"}
            continue
        local_path = assets_dir / f"{source_digest}{suffix}"
        try:
            _write_asset(local_path, body)
        except OSError as exc:
            materialized[index] = {**_clean_candidate(image), "asset_error": f"asset write failed: {exc}"}
            continue
        enriched = _finish_local_asset(
            image,
            body=body,
            content_type=content_type,
            local_path=local_path,
            from_cache=False,
            final_url=str(getattr(result, "final_url", "") or ""),
        )
        enriched["asset_retrieval_source"] = str(getattr(result, "retrieval_source", "") or "")
        enriched["asset_profile"] = str(getattr(result, "profile", "") or "")
        materialized[index] = enriched
        materialized_assets += 1

    return materialized