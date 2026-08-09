#!/usr/bin/env python3
"""Probe external comic metadata providers using a ComicPile JSON export."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_SEED = 20260807
USER_AGENT = os.getenv(
    "COMICPILE_METADATA_USER_AGENT",
    "ComicPileMetadataProbe/0.1 (set COMICPILE_METADATA_USER_AGENT with contact email)",
)


def norm(value: Any) -> str:
    text = str(value or "").casefold().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def issue_norm(value: Any) -> str:
    text = str(value or "").casefold().strip().lstrip("#")
    text = re.sub(r"\.0$", "", text)
    return re.sub(r"\s+", "", text)


def similarity(a: Any, b: Any) -> float:
    na, nb = norm(a), norm(b)
    return SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0


def first(data: Any, *paths: str) -> Any:
    for path in paths:
        cur = data
        try:
            for part in path.split("."):
                cur = cur[int(part)] if isinstance(cur, list) else cur[part]
            if cur not in (None, "", [], {}):
                return cur
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    return None


def items(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def names(value: Any) -> list[str]:
    out: list[str] = []
    for entry in items(value):
        name = first(entry, "name", "title") if isinstance(entry, dict) else entry
        if name and str(name) not in out:
            out.append(str(name))
    return out


def image(
    kind: str, url: Any, width: Any = None, height: Any = None
) -> dict[str, Any] | None:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    return {"type": kind, "url": url, "width": width, "height": height}


@dataclass
class Sample:
    thread_id: Any
    issue_id: Any
    title: str
    issue_number: str
    format: str
    thread_status: str
    issue_status: str
    position: Any = None


def blank_result(
    provider: str, configured: bool, attempted: bool = False
) -> dict[str, Any]:
    return {
        "provider": provider,
        "configured": configured,
        "attempted": attempted,
        "found": False,
        "usable": False,
        "classification": "not_configured" if not configured else "miss",
        "identity_confidence": 0.0,
        "matched_title": None,
        "matched_issue_number": None,
        "series_external_id": None,
        "issue_external_id": None,
        "cross_ids": {
            "comic_vine": None,
            "gcd": None,
            "metron": None,
            "wikidata": None,
            "isbn": [],
        },
        "publisher": None,
        "imprint": None,
        "dates": {},
        "creators": [],
        "characters": [],
        "teams": [],
        "story_arcs": [],
        "events": [],
        "descriptions": [],
        "images": [],
        "available_fields": [],
        "warnings": [],
        "error": None,
        "raw_cache_file": None,
        "candidates": [],
    }


class HttpClient:
    def __init__(self, cache_dir: Path, refresh: bool) -> None:
        self.cache_dir, self.refresh = cache_dir, refresh
        self.last_request: dict[str, float] = {}
        cache_dir.mkdir(parents=True, exist_ok=True)

    def get(
        self,
        provider: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        pace: float = 0.35,
    ) -> tuple[Any, str]:
        safe_params = {
            k: v
            for k, v in (params or {}).items()
            if v is not None and k.casefold() not in {"api_key", "key"}
        }
        fingerprint = json.dumps(
            [provider, endpoint, sorted(safe_params.items())],
            ensure_ascii=False,
            default=str,
        )
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()
        path = self.cache_dir / provider / f"{digest}.json"
        if path.exists() and not self.refresh:
            return json.loads(path.read_text(encoding="utf-8")), str(path)
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = endpoint + (("&" if "?" in endpoint else "?") + query if query else "")
        wait = pace - (time.monotonic() - self.last_request.get(provider, 0.0))
        if wait > 0:
            time.sleep(wait)
        request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        request_headers.update(headers or {})
        request = urllib.request.Request(url, headers=request_headers)
        attempts = 0
        while True:
            attempts += 1
            try:
                self.last_request[provider] = time.monotonic()
                with urllib.request.urlopen(request, timeout=25) as response:
                    raw = response.read().decode("utf-8", "replace")
                data = json.loads(raw)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                return data, str(path)
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempts < 3:
                    retry = exc.headers.get("Retry-After", "2")
                    try:
                        delay = min(float(retry), 30.0)
                    except ValueError:
                        delay = 2.0
                    time.sleep(delay)
                    continue
                body = exc.read(500).decode("utf-8", "replace")
                raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"request failed: {exc}") from exc


class Provider:
    name = "provider"
    collected_only = False

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    @property
    def configured(self) -> bool:
        return True

    def search(self, sample: Sample) -> dict[str, Any]:
        raise NotImplementedError

    def guarded_search(self, sample: Sample) -> dict[str, Any]:
        if not self.configured:
            return blank_result(self.name, False)
        try:
            result = self.search(sample)
            finish_result(result)
            return result
        except Exception as exc:  # keep the experiment running provider-by-provider
            result = blank_result(self.name, True, True)
            result.update(classification="error", error=str(exc))
            return result


def classify(
    title_score: float,
    issue_match: bool | None,
    *,
    weak_source: bool = False,
    ambiguous: bool = False,
    external_exact: bool = False,
) -> tuple[str, float, bool]:
    confidence = (
        title_score * 0.65
        + (0.30 if issue_match else 0.0)
        + (0.05 if external_exact else 0.0)
    )
    if weak_source:
        confidence = min(confidence, 0.62)
    if ambiguous:
        return "ambiguous", round(min(confidence, 0.69), 3), False
    if external_exact or (title_score >= 0.91 and issue_match):
        label = "exact"
    elif title_score >= 0.78 and issue_match:
        label = "strong"
    elif title_score >= 0.62 and (issue_match is not False):
        label = "plausible"
    else:
        label = "miss"
    usable = label in {"exact", "strong"} or (label == "plausible" and not weak_source)
    return label, round(min(confidence, 1.0), 3), usable


def finish_result(result: dict[str, Any]) -> None:
    result["images"] = [x for x in result.get("images", []) if x]
    fields = []
    for key in (
        "publisher",
        "imprint",
        "dates",
        "creators",
        "characters",
        "teams",
        "story_arcs",
        "events",
        "descriptions",
        "images",
    ):
        if result.get(key):
            fields.append(key)
    for key, value in result.get("cross_ids", {}).items():
        if value:
            fields.append(f"cross_ids.{key}")
    result["available_fields"] = sorted(set(fields))


class MetronProvider(Provider):
    name = "metron"

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self.base = os.getenv("METRON_BASE_URL", "https://metron.cloud").rstrip("/")
        self.token = os.getenv("METRON_API_TOKEN")
        self.username, self.password = (
            os.getenv("METRON_USERNAME"),
            os.getenv("METRON_PASSWORD"),
        )

    @property
    def configured(self) -> bool:
        return bool(self.token or (self.username and self.password))

    def headers(self) -> dict[str, str]:
        if self.token:
            # Metron tokens are commonly DRF tokens; Bearer is accepted by some deployments.
            return {"Authorization": f"Token {self.token}"}
        raw = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {raw}"}

    def search(self, sample: Sample) -> dict[str, Any]:
        result = blank_result(self.name, True, True)
        data, cache = self.http.get(
            self.name,
            f"{self.base}/api/series/",
            {"name": sample.title},
            self.headers(),
        )
        candidates = first(data, "results") or items(data)
        scored = sorted(
            [
                (similarity(sample.title, first(x, "name", "title")), x)
                for x in candidates
                if isinstance(x, dict)
            ],
            reverse=True,
            key=lambda x: x[0],
        )
        if not scored:
            result["raw_cache_file"] = cache
            return result
        result["candidates"] = [
            {
                "title": first(x, "name", "title"),
                "id": first(x, "id"),
                "score": round(s, 3),
            }
            for s, x in scored[:3]
        ]
        best_score, series = scored[0]
        ambiguous = len(scored) > 1 and scored[1][0] >= best_score - 0.04
        sid = first(series, "id")
        issues, issue_cache = self.http.get(
            self.name,
            f"{self.base}/api/issue/",
            {"series": sid, "number": sample.issue_number},
            self.headers(),
        )
        issue_candidates = [
            x
            for x in (first(issues, "results") or items(issues))
            if isinstance(x, dict)
        ]
        exacts = [
            x
            for x in issue_candidates
            if issue_norm(first(x, "number", "issue_number"))
            == issue_norm(sample.issue_number)
        ]
        issue = (
            exacts[0]
            if len(exacts) == 1
            else (issue_candidates[0] if len(issue_candidates) == 1 else None)
        )
        label, conf, usable = classify(
            best_score, bool(exacts), ambiguous=ambiguous or len(exacts) > 1
        )
        obj = issue or series
        publisher = first(
            obj, "publisher.name", "series.publisher.name", "publisher"
        ) or first(series, "publisher.name", "publisher")
        cross = {
            "comic_vine": first(obj, "cv_id", "comic_vine_id"),
            "gcd": first(obj, "gcd_id"),
            "metron": first(obj, "id"),
            "wikidata": None,
            "isbn": [],
        }
        result.update(
            found=True,
            usable=usable,
            classification=label,
            identity_confidence=conf,
            matched_title=first(series, "name", "title"),
            matched_issue_number=first(issue, "number", "issue_number")
            if issue
            else None,
            series_external_id=sid,
            issue_external_id=first(issue, "id") if issue else None,
            cross_ids=cross,
            publisher=publisher,
            imprint=first(obj, "imprint.name", "imprint"),
            dates={
                k: v
                for k, v in {
                    "cover_date": first(obj, "cover_date"),
                    "store_date": first(obj, "store_date"),
                    "foc_date": first(obj, "foc_date"),
                }.items()
                if v
            },
            creators=names(first(obj, "credits", "creators")),
            characters=names(first(obj, "characters")),
            teams=names(first(obj, "teams")),
            story_arcs=names(first(obj, "arcs", "story_arcs", "reading_lists")),
            events=names(first(obj, "events")),
            descriptions=names(first(obj, "description", "desc")),
            images=[
                image(
                    "issue_cover" if issue else "series_image",
                    first(obj, "image", "cover", "cover_url"),
                )
            ],
            raw_cache_file=issue_cache,
        )
        return result


class ComicVineProvider(Provider):
    name = "comic_vine"

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self.base = os.getenv(
            "COMICVINE_BASE_URL", "https://comicvine.gamespot.com/api"
        ).rstrip("/")
        self.key = os.getenv("COMICVINE_API_KEY")

    @property
    def configured(self) -> bool:
        return bool(self.key)

    def get(self, endpoint: str, params: dict[str, Any]) -> tuple[Any, str]:
        return self.http.get(
            self.name,
            f"{self.base}/{endpoint.lstrip('/')}",
            {**params, "api_key": self.key, "format": "json"},
            pace=1.05,
        )

    def search(self, sample: Sample) -> dict[str, Any]:
        result = blank_result(self.name, True, True)
        data, cache = self.get(
            "search/",
            {
                "query": sample.title,
                "resources": "volume",
                "limit": 8,
                "field_list": "id,name,start_year,publisher,image",
            },
        )
        volumes = [x for x in (first(data, "results") or []) if isinstance(x, dict)]
        scored = sorted(
            [(similarity(sample.title, x.get("name")), x) for x in volumes],
            reverse=True,
            key=lambda x: x[0],
        )
        if not scored:
            result["raw_cache_file"] = cache
            return result
        best_score, volume = scored[0]
        ambiguous = len(scored) > 1 and scored[1][0] >= best_score - 0.04
        result["candidates"] = [
            {
                "title": x.get("name"),
                "id": x.get("id"),
                "score": round(s, 3),
                "start_year": x.get("start_year"),
            }
            for s, x in scored[:3]
        ]
        fields = "id,name,issue_number,volume,image,cover_date,store_date,site_detail_url,description,person_credits,character_credits,team_credits,concept_credits,location_credits,story_arc_credits"
        issue_data, issue_cache = self.get(
            "issues/",
            {
                "filter": f"volume:{volume['id']},issue_number:{sample.issue_number}",
                "limit": 5,
                "field_list": fields,
            },
        )
        candidates = [
            x for x in (first(issue_data, "results") or []) if isinstance(x, dict)
        ]
        exacts = [
            x
            for x in candidates
            if issue_norm(x.get("issue_number")) == issue_norm(sample.issue_number)
        ]
        issue = (
            exacts[0]
            if len(exacts) == 1
            else (candidates[0] if len(candidates) == 1 else None)
        )
        label, conf, usable = classify(
            best_score, bool(exacts), ambiguous=ambiguous or len(exacts) > 1
        )
        obj = issue or {}
        publisher = first(volume, "publisher.name")
        vimg = first(
            volume, "image.original_url", "image.super_url", "image.medium_url"
        )
        iimg = first(obj, "image.original_url", "image.super_url", "image.medium_url")
        result.update(
            found=True,
            usable=usable,
            classification=label,
            identity_confidence=conf,
            matched_title=volume.get("name"),
            matched_issue_number=obj.get("issue_number"),
            series_external_id=volume.get("id"),
            issue_external_id=obj.get("id"),
            cross_ids={
                "comic_vine": obj.get("id") or volume.get("id"),
                "gcd": None,
                "metron": None,
                "wikidata": None,
                "isbn": [],
            },
            publisher=publisher,
            dates={
                k: v
                for k, v in {
                    "cover_date": obj.get("cover_date"),
                    "store_date": obj.get("store_date"),
                    "start_year": volume.get("start_year"),
                }.items()
                if v
            },
            creators=names(obj.get("person_credits")),
            characters=names(obj.get("character_credits")),
            teams=names(obj.get("team_credits")),
            story_arcs=names(obj.get("story_arc_credits")),
            events=[],
            descriptions=names(obj.get("description")),
            images=[
                image("issue_cover", iimg),
                image("series_image", vimg),
                image("publisher_logo", first(volume, "publisher.image.original_url")),
            ],
            raw_cache_file=issue_cache,
        )
        concepts = names(obj.get("concept_credits"))
        locations = names(obj.get("location_credits"))
        if concepts:
            result["available_fields"].append("concepts")
            result["concepts"] = concepts
        if locations:
            result["available_fields"].append("locations")
            result["locations"] = locations
        return result


COLLECTED_RE = re.compile(
    r"\b(omnibus|trade|tpb|hardcover|hc|collection|collected|complete|volume|vol\.?|graphic novel)\b",
    re.I,
)


class GoogleBooksProvider(Provider):
    name, collected_only = "google_books", True

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self.key = os.getenv("GOOGLE_BOOKS_API_KEY")

    def search(self, sample: Sample) -> dict[str, Any]:
        result = blank_result(self.name, True, True)
        query = f'intitle:"{sample.title}" "{sample.issue_number}"'
        params = {"q": query, "maxResults": 10, "printType": "books"}
        if self.key:
            params["key"] = self.key
        data, cache = self.http.get(
            self.name, "https://www.googleapis.com/books/v1/volumes", params
        )
        candidates = [x for x in (data.get("items") or []) if isinstance(x, dict)]
        scored = sorted(
            [
                (similarity(sample.title, first(x, "volumeInfo.title")), x)
                for x in candidates
            ],
            reverse=True,
            key=lambda x: x[0],
        )
        if not scored:
            result["raw_cache_file"] = cache
            return result
        score, book = scored[0]
        info = book.get("volumeInfo", {})
        likely_collected = bool(COLLECTED_RE.search(sample.title + " " + sample.format))
        label, conf, usable = classify(
            score,
            None,
            weak_source=not likely_collected,
            ambiguous=len(scored) > 1 and scored[1][0] >= score - 0.04,
        )
        ids = [
            x.get("identifier")
            for x in info.get("industryIdentifiers", [])
            if str(x.get("type", "")).startswith("ISBN") and x.get("identifier")
        ]
        result.update(
            found=True,
            usable=usable and likely_collected,
            classification=label,
            identity_confidence=conf,
            matched_title=info.get("title"),
            series_external_id=book.get("id"),
            cross_ids={
                "comic_vine": None,
                "gcd": None,
                "metron": None,
                "wikidata": None,
                "isbn": ids,
            },
            publisher=info.get("publisher"),
            dates={"published_date": info.get("publishedDate")}
            if info.get("publishedDate")
            else {},
            creators=names(info.get("authors")),
            descriptions=names(info.get("description")),
            images=[
                image(
                    "series_image",
                    first(
                        info,
                        "imageLinks.extraLarge",
                        "imageLinks.large",
                        "imageLinks.thumbnail",
                    ),
                )
            ],
            raw_cache_file=cache,
            candidates=[
                {
                    "title": first(x, "volumeInfo.title"),
                    "id": x.get("id"),
                    "score": round(s, 3),
                }
                for s, x in scored[:3]
            ],
        )
        if not likely_collected:
            result["warnings"].append(
                "Ordinary single issues are low-confidence in Google Books."
            )
        return result


class OpenLibraryProvider(Provider):
    name, collected_only = "open_library", True

    def search(self, sample: Sample) -> dict[str, Any]:
        result = blank_result(self.name, True, True)
        data, cache = self.http.get(
            self.name,
            "https://openlibrary.org/search.json",
            {
                "title": sample.title,
                "limit": 10,
                "fields": "key,title,author_name,publisher,first_publish_year,isbn,cover_i,edition_key",
            },
        )
        docs = [x for x in (data.get("docs") or []) if isinstance(x, dict)]
        scored = sorted(
            [(similarity(sample.title, x.get("title")), x) for x in docs],
            reverse=True,
            key=lambda x: x[0],
        )
        if not scored:
            result["raw_cache_file"] = cache
            return result
        score, work = scored[0]
        likely_collected = bool(COLLECTED_RE.search(sample.title + " " + sample.format))
        label, conf, usable = classify(
            score,
            None,
            weak_source=not likely_collected,
            ambiguous=len(scored) > 1 and scored[1][0] >= score - 0.04,
        )
        cover_id = work.get("cover_i")
        result.update(
            found=True,
            usable=usable and likely_collected,
            classification=label,
            identity_confidence=conf,
            matched_title=work.get("title"),
            series_external_id=work.get("key"),
            cross_ids={
                "comic_vine": None,
                "gcd": None,
                "metron": None,
                "wikidata": None,
                "isbn": work.get("isbn", []),
            },
            publisher=first(work, "publisher.0"),
            dates={"first_publish_year": work.get("first_publish_year")}
            if work.get("first_publish_year")
            else {},
            creators=names(work.get("author_name")),
            images=[
                image(
                    "series_image",
                    f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg",
                )
                if cover_id
                else None
            ],
            raw_cache_file=cache,
            candidates=[
                {"title": x.get("title"), "id": x.get("key"), "score": round(s, 3)}
                for s, x in scored[:3]
            ],
        )
        if not likely_collected:
            result["warnings"].append(
                "Open Library is evaluated as a collected-edition source, not an issue source."
            )
        return result


class WikidataProvider(Provider):
    name = "wikidata"

    def search(self, sample: Sample) -> dict[str, Any]:
        result = blank_result(self.name, True, True)
        data, cache = self.http.get(
            self.name,
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbsearchentities",
                "search": sample.title,
                "language": "en",
                "format": "json",
                "limit": 6,
                "type": "item",
            },
        )
        found = [x for x in (data.get("search") or []) if isinstance(x, dict)]
        scored = sorted(
            [(similarity(sample.title, x.get("label")), x) for x in found],
            reverse=True,
            key=lambda x: x[0],
        )
        if not scored:
            result["raw_cache_file"] = cache
            return result
        score, entity = scored[0]
        ambiguous = len(scored) > 1 and scored[1][0] >= score - 0.04
        entity_data, entity_cache = self.http.get(
            self.name,
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbgetentities",
                "ids": entity["id"],
                "props": "claims|sitelinks|descriptions",
                "languages": "en",
                "format": "json",
            },
        )
        obj = first(entity_data, f"entities.{entity['id']}") or {}
        claims = obj.get("claims", {})

        def claim_id(prop: str) -> Any:
            return first(claims, f"{prop}.0.mainsnak.datavalue.value.id")

        def claim_text(prop: str) -> Any:
            return first(claims, f"{prop}.0.mainsnak.datavalue.value")

        media_names = [claim_text("P154"), claim_text("P18")]
        media_urls = []
        for filename in media_names:
            if filename:
                media_urls.append(
                    "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
                    + urllib.parse.quote(str(filename))
                )
        label, conf, _ = classify(score, None, weak_source=True, ambiguous=ambiguous)
        result.update(
            found=True,
            usable=score >= 0.78 and not ambiguous,
            classification=label if label != "miss" else "plausible",
            identity_confidence=conf,
            matched_title=entity.get("label"),
            series_external_id=entity.get("id"),
            cross_ids={
                "comic_vine": None,
                "gcd": None,
                "metron": None,
                "wikidata": entity.get("id"),
                "isbn": [],
            },
            descriptions=names(entity.get("description")),
            images=[image("entity_image", u) for u in media_urls],
            raw_cache_file=entity_cache,
            candidates=[
                {
                    "title": x.get("label"),
                    "id": x.get("id"),
                    "description": x.get("description"),
                    "score": round(s, 3),
                }
                for s, x in scored[:3]
            ],
            warnings=[
                "Entity-level match only; not evidence of individual issue identity."
            ],
        )
        if claim_id("P749"):
            result["parent_company_wikidata_id"] = claim_id("P749")
        if claim_text("P856"):
            result["official_website"] = claim_text("P856")
        return result


class GCDAdapter(Provider):
    """Intentional placeholder for a future local GCD database adapter."""

    name = "gcd"

    @property
    def configured(self) -> bool:
        return False

    def search(self, sample: Sample) -> dict[str, Any]:
        return blank_result(self.name, False)


def load_samples(path: Path, include_read: bool) -> list[Sample]:
    data = json.loads(path.read_text(encoding="utf-8"))[0]

    if not isinstance(data.get("queue"), list):
        raise ValueError("export does not contain a queue array")
    out = []
    for thread in data["queue"]:
        for issue in thread.get("issues", []):
            status = str(issue.get("status", ""))
            if not include_read and status.casefold() in {"read", "completed"}:
                continue
            out.append(
                Sample(
                    thread.get("thread_id"),
                    issue.get("issue_id"),
                    str(thread.get("title", "")),
                    str(issue.get("issue_number", "")),
                    str(thread.get("format", "")),
                    str(thread.get("status", "")),
                    status,
                    issue.get("position"),
                )
            )
    return out


def breadth_sample(samples: list[Sample], count: int, seed: int) -> list[Sample]:
    rng = random.Random(seed)
    by_thread: dict[Any, list[Sample]] = {}
    for sample in samples:
        by_thread.setdefault(sample.thread_id, []).append(sample)
    thread_ids = list(by_thread)
    rng.shuffle(thread_ids)
    chosen = []
    for tid in thread_ids:
        rng.shuffle(by_thread[tid])
        chosen.append(by_thread[tid].pop())
        if len(chosen) >= count:
            return chosen
    leftovers = [x for group in by_thread.values() for x in group]
    rng.shuffle(leftovers)
    return chosen + leftovers[: max(0, count - len(chosen))]


def download_images(records: list[dict[str, Any]], output: Path) -> None:
    folder = output / "images"
    folder.mkdir(parents=True, exist_ok=True)
    for record in records:
        sample = record["sample"]
        for result in record["providers"]:
            if not result.get("usable"):
                continue
            for idx, img in enumerate(result.get("images", [])):
                try:
                    suffix = Path(urllib.parse.urlparse(img["url"]).path).suffix.lower()
                    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                        suffix = ".jpg"
                    name = f"{sample['issue_id']}_{result['provider']}_{img['type']}_{idx}{suffix}"
                    req = urllib.request.Request(
                        img["url"], headers={"User-Agent": USER_AGENT}
                    )
                    with urllib.request.urlopen(req, timeout=20) as response:
                        payload = response.read(12_000_000)
                    (folder / name).write_bytes(payload)
                    img["downloaded_file"] = str(folder / name)
                except Exception as exc:
                    result["warnings"].append(f"image download failed: {exc}")


def external_count(result: dict[str, Any]) -> int:
    return sum(
        len(v) if isinstance(v, list) else 1
        for v in result.get("cross_ids", {}).values()
        if v
    )


def write_outputs(
    records: list[dict[str, Any]], providers: list[Provider], output: Path, seed: int
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": seed,
        "sample_size": len(records),
        "providers": [p.name for p in providers],
        "samples": records,
    }
    (output / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    columns = "thread_id issue_id title issue_number format provider classification identity_confidence found usable matched_title matched_issue_number publisher external_id_count available_field_count image_count has_issue_cover has_publisher_logo creator_count character_count story_arc_count event_count error".split()
    with (output / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            s = record["sample"]
            for r in record["providers"]:
                imgs = r.get("images", [])
                writer.writerow(
                    {
                        **{k: s.get(k) for k in columns},
                        "provider": r["provider"],
                        "classification": r["classification"],
                        "identity_confidence": r["identity_confidence"],
                        "found": r["found"],
                        "usable": r["usable"],
                        "matched_title": r.get("matched_title"),
                        "matched_issue_number": r.get("matched_issue_number"),
                        "publisher": r.get("publisher"),
                        "external_id_count": external_count(r),
                        "available_field_count": len(r.get("available_fields", [])),
                        "image_count": len(imgs),
                        "has_issue_cover": any(
                            x["type"] == "issue_cover" for x in imgs
                        ),
                        "has_publisher_logo": any(
                            x["type"] == "publisher_logo" for x in imgs
                        ),
                        "creator_count": len(r.get("creators", [])),
                        "character_count": len(r.get("characters", [])),
                        "story_arc_count": len(r.get("story_arcs", [])),
                        "event_count": len(r.get("events", [])),
                        "error": r.get("error"),
                    }
                )
    write_report(records, providers, output / "report.md")


def write_report(
    records: list[dict[str, Any]], providers: list[Provider], path: Path
) -> None:
    all_results = [r for rec in records for r in rec["providers"]]
    configured = [p.name for p in providers if p.configured]
    skipped = [p.name for p in providers if not p.configured]
    categories: dict[str, Callable[[dict[str, Any]], bool]] = {
        "Covers": lambda r: any(x["type"] == "issue_cover" for x in r["images"]),
        "Logos": lambda r: any(
            x["type"] in {"publisher_logo", "imprint_logo"} for x in r["images"]
        ),
        "Creators": lambda r: bool(r["creators"]),
        "Characters": lambda r: bool(r["characters"]),
        "Story arcs": lambda r: bool(r["story_arcs"]),
        "Events": lambda r: bool(r["events"]),
        "Cross IDs": lambda r: external_count(r) > 1,
    }
    rows = []
    stats: dict[str, dict[str, int]] = {}
    for p in providers:
        prs = [r for r in all_results if r["provider"] == p.name and r["attempted"]]
        denom = len(prs)
        values = {
            "attempted": denom,
            "exact_strong": sum(
                r["classification"] in {"exact", "strong"} for r in prs
            ),
            "usable": sum(bool(r["usable"]) for r in prs),
            **{k: sum(fn(r) for r in prs) for k, fn in categories.items()},
        }
        stats[p.name] = values
        pct = lambda n: f"{n}/{denom} ({n / denom:.0%})" if denom else "skipped"
        rows.append(
            f"| {p.name} | {pct(values['exact_strong'])} | {pct(values['usable'])} | {pct(values['Covers'])} | {pct(values['Logos'])} | {pct(values['Creators'])} | {pct(values['Characters'])} | {pct(values['Cross IDs'])} |"
        )
    best = {}
    for category in categories:
        contenders = [
            (stats[p.name].get(category, 0), p.name)
            for p in providers
            if stats[p.name]["attempted"]
        ]
        best[category] = (
            max(contenders)[1]
            if contenders and max(contenders)[0] > 0
            else "none observed"
        )
    primary_rank = sorted(
        [
            (
                stats[p.name]["usable"] * 3
                + stats[p.name]["exact_strong"] * 2
                + sum(stats[p.name].get(c, 0) for c in categories),
                p.name,
            )
            for p in providers
            if stats[p.name]["attempted"]
        ],
        reverse=True,
    )
    primary = primary_rank[0][1] if primary_rank else "none"
    fallback = primary_rank[1][1] if len(primary_rank) > 1 else "none"
    ambiguous = [
        (rec["sample"], r)
        for rec in records
        for r in rec["providers"]
        if r["classification"] == "ambiguous"
    ]
    errors = [
        (rec["sample"], r)
        for rec in records
        for r in rec["providers"]
        if r.get("error")
    ]
    observed_fields = sorted(
        {
            f
            for r in all_results
            if r.get("usable")
            for f in r.get("available_fields", [])
        }
    )
    lines = [
        "# ComicPile metadata-provider probe",
        "",
        f"- Sample size: {len(records)}",
        f"- Providers configured: {', '.join(configured) or 'none'}",
        f"- Providers skipped: {', '.join(skipped) or 'none'}",
        "",
        "## Coverage by provider",
        "",
        "| Provider | Exact/strong | Usable | Covers | Logos | Creators | Characters | Cross IDs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        *rows,
        "",
        "## Category findings",
        "",
        *[f"- Best for {k.casefold()}: **{v}**" for k, v in best.items()],
        "",
        "## Recommendations from this run",
        "",
        f"- Recommended primary metadata provider: **{primary}**",
        f"- Recommended fallback provider: **{fallback}**",
        "- Collected-edition-focused providers: **google_books, open_library**. Their issue-level confidence is deliberately capped.",
        "- Entity/logo-focused provider: **wikidata**. Its matches do not prove individual issue identity.",
        "- GCD was not scraped. GCD coverage is counted only when another provider supplied a GCD cross-ID.",
        "",
        "## Ambiguous matches",
        "",
        *(
            [
                f"- {s['title']} #{s['issue_number']} via {r['provider']}: {json.dumps(r.get('candidates', []), ensure_ascii=False)}"
                for s, r in ambiguous
            ]
            or ["None."]
        ),
        "",
        "## Provider errors",
        "",
        *(
            [
                f"- {s['title']} #{s['issue_number']} via {r['provider']}: {r['error']}"
                for s, r in errors
            ]
            or ["None."]
        ),
        "",
        "## Concrete schema recommendations",
        "",
    ]
    if observed_fields:
        lines += [
            "Fields below were observed on usable results, so they are candidates for provider-neutral storage:",
            "",
            *[f"- `{f}`" for f in observed_fields],
            "",
            "Keep provider payloads and identity decisions separate. Store provider, external ID, match classification, confidence, confirmation status, and fetched-at time alongside normalized metadata. Use a separate image table with type, URL, dimensions, provider, and retrieval time. Model cross-IDs as repeatable `(namespace, value)` rows rather than fixed columns. Preserve ambiguous candidates until a user confirms identity.",
        ]
    else:
        lines.append(
            "No usable provider fields were observed, so this run does not justify adding normalized metadata columns yet."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--sample-size", type=int, default=25)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--providers",
        default="metron,comic_vine,google_books,open_library,wikidata,gcd",
        help="comma-separated provider names",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("metadata_probe_output")
    )
    parser.add_argument("--include-read", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--download-images", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_size < 1:
        raise SystemExit("--sample-size must be positive")
    http = HttpClient(args.output_dir / "cache", args.refresh_cache)
    available = {
        p.name: p
        for p in [
            MetronProvider(http),
            ComicVineProvider(http),
            GoogleBooksProvider(http),
            OpenLibraryProvider(http),
            WikidataProvider(http),
            GCDAdapter(http),
        ]
    }
    requested = [x.strip() for x in args.providers.split(",") if x.strip()]
    unknown = sorted(set(requested) - set(available))
    if unknown:
        raise SystemExit(f"unknown providers: {', '.join(unknown)}")
    providers = [available[x] for x in requested]
    samples = breadth_sample(
        load_samples(args.export, args.include_read), args.sample_size, args.seed
    )
    if not samples:
        raise SystemExit("no eligible issues found in export")
    records = []
    for index, sample in enumerate(samples, 1):
        print(f"[{index}/{len(samples)}] {sample.title} #{sample.issue_number}")
        results = []
        for provider in providers:
            result = provider.guarded_search(sample)
            results.append(result)
            details = []
            if any(x["type"] == "issue_cover" for x in result["images"]):
                details.append("cover")
            if result["creators"]:
                details.append("creators")
            if result["cross_ids"].get("gcd"):
                details.append("GCD ID")
            suffix = f", {', '.join(details)}" if details else ""
            print(f"  {provider.name}: {result['classification']}{suffix}")
        records.append({"sample": asdict(sample), "providers": results})
    if args.download_images:
        download_images(records, args.output_dir)
    write_outputs(records, providers, args.output_dir, args.seed)
    all_results = [r for rec in records for r in rec["providers"]]
    print("\nSamples tested:", len(samples))
    print(
        "Providers configured:",
        ", ".join(p.name for p in providers if p.configured) or "none",
    )
    print("Exact matches:", sum(r["classification"] == "exact" for r in all_results))
    print("Strong matches:", sum(r["classification"] == "strong" for r in all_results))
    print(
        "Ambiguous matches:",
        sum(r["classification"] == "ambiguous" for r in all_results),
    )
    print("Usable metadata results:", sum(bool(r["usable"]) for r in all_results))
    print(
        "Issue covers found:",
        sum(any(x["type"] == "issue_cover" for x in r["images"]) for r in all_results),
    )
    print(
        "Publisher logos found:",
        sum(
            any(x["type"] == "publisher_logo" for x in r["images"]) for r in all_results
        ),
    )
    print("Cross-provider IDs found:", sum(external_count(r) > 1 for r in all_results))
    print("Report path:", args.output_dir / "report.md")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("interrupted")
