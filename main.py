#!/usr/bin/python

import json
from typing import List, Optional, Tuple
import urllib.parse
import random
import http.client
import sys
import os
import re
import hashlib
import time
import pathlib
import threading
import traceback

CYRILLIC_RE = re.compile(r'[Ѐ-ӿԀ-ԯ]')

# Voice map for macOS `say`. Falls back to "Samantha" (US English) if lang missing.
SAY_VOICES = {
    "ru": "Milena",
    "en": "Samantha",
    "fr": "Audrey",
    "de": "Anna",
    "es": "Mónica",
    "it": "Alice",
    "pt": "Joana",
    "pl": "Zosia",
    "ja": "Kyoko",
    "ko": "Yuna",
    "zh-CN": "Tingting",
    "zh-TW": "Meijia",
    "nl": "Xander",
    "sv": "Alva",
    "tr": "Yelda",
    "ar": "Maged",
    "he": "Carmit",
    "hi": "Lekha",
    "th": "Kanya",
    "el": "Melina",
}

CACHE_DIR = pathlib.Path(os.environ.get(
    "GTRANSLATE_CACHE_DIR",
    pathlib.Path.home() / "Library" / "Caches" / "gtranslate",
))
CACHE_TTL_SEC = 7 * 24 * 3600
CACHE_MAX_ENTRIES = int(os.environ.get("GTRANSLATE_CACHE_MAX", "1000"))
CACHE_PRUNE_PROB = 0.02  # 2% chance per put to scan + evict


def _cache_path(text: str, target: str) -> pathlib.Path:
    h = hashlib.sha256(f"{target}\x00{text}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.json"


def cache_get(text: str, target: str):
    p = _cache_path(text, target)
    try:
        if time.time() - p.stat().st_mtime > CACHE_TTL_SEC:
            return None
        with p.open("rb") as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _cache_prune():
    """Drop oldest entries when over cap. Cheap: stat-sort + unlink overflow."""
    try:
        files = list(CACHE_DIR.glob("*.json"))
        if len(files) <= CACHE_MAX_ENTRIES:
            return
        files.sort(key=lambda p: p.stat().st_mtime)
        for p in files[: len(files) - CACHE_MAX_ENTRIES]:
            try:
                p.unlink()
            except OSError:
                pass
    except OSError:
        pass


def cache_put(text: str, target: str, payload):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _cache_path(text, target)
        tmp = p.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        tmp.replace(p)
        if random.random() < CACHE_PRUNE_PROB:
            _cache_prune()
    except OSError:
        pass


class Translate:
    """
    Translate API
    Thanks to Telegram MacOS client for the idea

    https://github.com/TelegramOrg/Telegram-macos-Swift/blob/67e4cf8de2f060ec8152ce68562c9489a6073534/packages/Translate/Sources/Translate/Translate.swift
    """

    languages = {
        "af",
        "sq",
        "am",
        "ar",
        "hy",
        "as",
        "ay",
        "az",
        "bm",
        "eu",
        "be",
        "bn",
        "bho",
        "bs",
        "bg",
        "ca",
        "ceb",
        "zh-CN",
        "zh-TW",
        "co",
        "hr",
        "cs",
        "da",
        "dv",
        "doi",
        "nl",
        "en",
        "eo",
        "et",
        "ee",
        "fil",
        "fi",
        "fr",
        "fy",
        "gl",
        "ka",
        "de",
        "el",
        "gn",
        "gu",
        "ht",
        "ha",
        "haw",
        "he",
        "hi",
        "hmn",
        "hu",
        "is",
        "ig",
        "ilo",
        "id",
        "ga",
        "it",
        "ja",
        "jv",
        "kn",
        "kk",
        "km",
        "rw",
        "gom",
        "ko",
        "kri",
        "ku",
        "ckb",
        "ky",
        "lo",
        "la",
        "lv",
        "ln",
        "lt",
        "lg",
        "lb",
        "mk",
        "mai",
        "mg",
        "ms",
        "ml",
        "mt",
        "mi",
        "mr",
        "mni-Mtei",
        "lus",
        "mn",
        "my",
        "ne",
        "no",
        "ny",
        "or",
        "om",
        "ps",
        "fa",
        "pl",
        "pt",
        "pa",
        "qu",
        "ro",
        "ru",
        "sm",
        "sa",
        "gd",
        "nso",
        "sr",
        "st",
        "sn",
        "sd",
        "si",
        "sk",
        "sl",
        "so",
        "es",
        "su",
        "sw",
        "sv",
        "tl",
        "tg",
        "ta",
        "tt",
        "te",
        "th",
        "ti",
        "ts",
        "tr",
        "tk",
        "ak",
        "uk",
        "ur",
        "ug",
        "uz",
        "vi",
        "cy",
        "xh",
        "yi",
        "yo",
        "zu",
    }


    user_agent = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.55 Safari/537.36"
    ]

    def __init__(self, lang: str = "en"):
        if lang not in self.languages:
            raise ValueError(f"Language {lang} is not supported")
        self.lang = lang

    @classmethod
    def _get_user_agent(cls):
        return random.choice(cls.user_agent)

    def _generate_url(self, text):
        text_encoded = urllib.parse.quote(text)
        return (
            "translate.googleapis.com",
            f"/translate_a/single?client=gtx&sl=auto&tl={self.lang}"
            f"&dt=t&dt=at&dt=bd&ie=UTF-8&oe=UTF-8&q={text_encoded}",
        )

    def _get_request(self, text):
        url, path = self._generate_url(text)
        conn = http.client.HTTPSConnection(url, timeout=2)
        try:
            headers = {"User-Agent": self._get_user_agent()}
            conn.request("GET", path, headers=headers)
            res = conn.getresponse()
            if res.status != 200:
                raise RuntimeError(f"HTTP {res.status}")
            return json.loads(res.read())
        finally:
            conn.close()

    def _parse_response(self, data) -> dict:
        # gtx /translate_a/single?dt=t&dt=at&dt=bd shape:
        #   [ [[trans, orig, ...], ...],      # main sentences
        #     [ [pos, [words], ...], ...],    # bilingual dict (dt=bd) or None
        #     detected_src_lang,
        #     ..., ..., [ [orig, null, [[alt, ...], ...]] ],  # alt translations (dt=at) at idx 5
        #     ... ]
        result = {"text": "", "src": "unknown", "alternatives": [], "dict": []}
        if not isinstance(data, list) or not data:
            return result
        try:
            sentences = data[0] or []
            result["text"] = "".join(
                s[0] for s in sentences if isinstance(s, list) and s and s[0]
            )
            if len(data) > 2 and isinstance(data[2], str):
                result["src"] = data[2]
            dict_section = data[1] if len(data) > 1 else None
            if isinstance(dict_section, list):
                for entry in dict_section:
                    if isinstance(entry, list) and len(entry) >= 2:
                        pos = entry[0] if isinstance(entry[0], str) else ""
                        words = entry[1] if isinstance(entry[1], list) else []
                        words = [w for w in words if isinstance(w, str)]
                        if pos and words:
                            result["dict"].append((pos, words))
            alt_section = data[5] if len(data) > 5 else None
            if isinstance(alt_section, list):
                seen = {result["text"]}
                for group in alt_section:
                    if not (isinstance(group, list) and len(group) >= 3):
                        continue
                    candidates = group[2]
                    if not isinstance(candidates, list):
                        continue
                    for cand in candidates:
                        if isinstance(cand, list) and cand and isinstance(cand[0], str):
                            word = cand[0]
                            if word and word not in seen:
                                seen.add(word)
                                result["alternatives"].append(word)
        except (TypeError, IndexError, KeyError):
            pass
        return result

    def get_translation(self, text: str) -> dict:
        cached = cache_get(text, self.lang)
        if cached is not None:
            return cached
        parsed = self._parse_response(self._get_request(text))
        cache_put(text, self.lang, parsed)
        return parsed


LANG_OVERRIDE_RE = re.compile(r'^:([a-zA-Z-]{2,7})\s+(.+)$', re.DOTALL)


def parse_override(text: str) -> Tuple[Optional[str], str]:
    """Strip leading ':<lang> ' override. Returns (forced_lang_or_None, remaining_text)."""
    m = LANG_OVERRIDE_RE.match(text)
    if not m:
        return None, text
    lang = m.group(1)
    # Normalize zh-cn → zh-CN; otherwise lowercase.
    if "-" in lang:
        a, b = lang.split("-", 1)
        lang = f"{a.lower()}-{b.upper()}"
    else:
        lang = lang.lower()
    if lang not in Translate.languages:
        return None, text  # invalid override → treat as text
    return lang, m.group(2)


def pick_target(text: str, out_lang: str, in_lang: str) -> str:
    cyrillic = bool(CYRILLIC_RE.search(text))
    if out_lang == "ru":
        return in_lang if cyrillic else out_lang
    if in_lang == "ru":
        return out_lang if cyrillic else in_lang
    return in_lang if cyrillic else out_lang


def reverse_target(forward_target: str, out_lang: str, in_lang: str) -> str:
    if forward_target == out_lang:
        return in_lang
    if forward_target == in_lang:
        return out_lang
    return out_lang


def _fetch_back(text: str, lang: str, holder: dict):
    try:
        holder["result"] = Translate(lang).get_translation(text)
    except Exception:
        holder["result"] = None


def build_items(parsed: dict, target: str, back_target: str, back_text: Optional[str]) -> list:
    items = []
    src = parsed.get("src", "??")
    main_text = parsed.get("text") or ""
    arrow = f"{src} → {target}"
    back_hint = f"⌘↩ copy back-translation ({back_target}): {back_text}" if back_text else f"⌘↩ back-translate to {back_target}"
    cmd_mod = {
        "arg": back_text or main_text,
        "subtitle": back_hint,
        "valid": bool(back_text),
    }
    voice = SAY_VOICES.get(target, "Samantha")

    def row(title: str, subtitle: str, arg: str) -> dict:
        return {
            "title": title,
            "subtitle": subtitle,
            "arg": arg,
            "valid": bool(arg),
            "variables": {"speak_voice": voice},
            "mods": {
                "cmd": cmd_mod,
                "ctrl": {"arg": arg, "subtitle": f"🔊 speak ({voice})", "valid": bool(arg)},
            },
        }

    items.append(row(main_text or "(no translation)", arrow, main_text))
    for alt in parsed.get("alternatives", []):
        items.append(row(alt, f"alternative · {arrow}", alt))
    for pos, words in parsed.get("dict", []):
        joined = ", ".join(words)
        items.append(row(joined, f"{pos} · {arrow}", joined))
    return items


def error_output(msg: str, detail: str = "") -> str:
    return json.dumps({"items": [{
        "title": msg,
        "subtitle": detail,
        "valid": False,
        "icon": {"type": "default"},
    }]}, ensure_ascii=False)


def main_entry(text: str) -> str:
    text = text.strip()
    if not text:
        return error_output("Type text to translate", "")
    try:
        out_lang = os.environ["output_language"]
        in_lang = os.environ["input_language"]
    except KeyError as e:
        return error_output("Missing config variable", f"{e}: set in Alfred workflow preferences")

    forced, text = parse_override(text)
    target = forced if forced else pick_target(text, out_lang, in_lang)
    back_target = reverse_target(target, out_lang, in_lang)

    try:
        parsed = Translate(target).get_translation(text)
    except (RuntimeError, OSError, json.JSONDecodeError) as e:
        return error_output("Translation failed", f"{type(e).__name__}: {e}")
    except ValueError as e:
        return error_output("Unsupported language", str(e))

    back_text = None
    main_text = parsed.get("text") or ""
    if main_text and target != back_target:
        holder: dict = {}
        t = threading.Thread(target=_fetch_back, args=(main_text, back_target, holder), daemon=True)
        t.start()
        t.join(timeout=4.5)
        bt = holder.get("result")
        back_text = (bt or {}).get("text") if isinstance(bt, dict) else None

    items = build_items(parsed, target, back_target, back_text)
    return json.dumps({"items": items}, ensure_ascii=False)


if __name__ == "__main__":
    try:
        print(main_entry(" ".join(sys.argv[1:])))
    except Exception as e:
        print(error_output("Workflow crashed", f"{type(e).__name__}: {e}"))
        traceback.print_exc(file=sys.stderr)
