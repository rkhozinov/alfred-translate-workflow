#!/usr/bin/python

import json
from typing import List
import urllib.parse
import random
import http.client
import sys
import os
import re
import hashlib
import time
import pathlib

CYRILLIC_RE = re.compile(r'[Ѐ-ӿԀ-ԯ]')

CACHE_DIR = pathlib.Path(os.environ.get(
    "GTRANSLATE_CACHE_DIR",
    pathlib.Path.home() / "Library" / "Caches" / "gtranslate",
))
CACHE_TTL_SEC = 7 * 24 * 3600


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


def cache_put(text: str, target: str, payload):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _cache_path(text, target)
        tmp = p.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        tmp.replace(p)
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
            "clients5.google.com",
            f"/translate_a/t?client=dict-chrome-ex&sl=auto&tl={self.lang}&q={text_encoded}",
        )

    def _get_request(self, text):
        url, path = self._generate_url(text)
        conn = http.client.HTTPSConnection(url, timeout=5)
        try:
            headers = {"User-Agent": self._get_user_agent()}
            conn.request("GET", path, headers=headers)
            res = conn.getresponse()
            if res.status != 200:
                raise RuntimeError(f"HTTP Error: {res.status}")
            return json.loads(res.read())
        finally:
            conn.close()

    def _parse_response(self, data: List) -> tuple:
        # clients5 endpoint shape: [[translation, lang]]  OR  {"sentences":[{"trans":..,"orig":..}],"src":..}
        if isinstance(data, list) and data and isinstance(data[0], list):
            translated_text = data[0][0] if data[0] else ""
            detected_lang = data[0][1] if len(data[0]) > 1 else "unknown"
            return detected_lang, [translated_text]
        if isinstance(data, dict) and "sentences" in data:
            translated_text = "".join(s.get("trans", "") for s in data["sentences"])
            detected_lang = data.get("src", "unknown")
            return detected_lang, [translated_text]
        return "unknown", [""]

    def get_translation(self, text: str):
        cached = cache_get(text, self.lang)
        if cached is not None:
            return tuple(cached)
        result = self._parse_response(self._get_request(text))
        cache_put(text, self.lang, list(result))
        return result


def generate_worflow_output(translations: List[str]):
    return json.dumps({
        "items": [
            {
                "title": translation,
                "subtitle": "",
                "arg": translation,
            }
            for translation in translations
        ]
    }, ensure_ascii=False)


def pick_target(text: str, out_lang: str, in_lang: str) -> str:
    cyrillic = bool(CYRILLIC_RE.search(text))
    if out_lang == "ru":
        return in_lang if cyrillic else out_lang
    if in_lang == "ru":
        return out_lang if cyrillic else in_lang
    return in_lang if cyrillic else out_lang


def main_entry(text: str) -> str:
    out_lang = os.environ["output_language"]
    in_lang = os.environ["input_language"]
    target = pick_target(text, out_lang, in_lang)
    _, translate = Translate(target).get_translation(text)
    return generate_worflow_output(translate)


if __name__ == "__main__":
    print(main_entry(' '.join(sys.argv[1:])))
