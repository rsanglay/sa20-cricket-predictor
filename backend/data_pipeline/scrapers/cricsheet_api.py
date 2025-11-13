"""Utilities for downloading and parsing Cricsheet datasets."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests


@dataclass
class CricsheetAPI:
    """Minimal wrapper for working with Cricsheet download archives."""

    base_url: str = "https://cricsheet.org/downloads"

    def zip_filename(self, competition: str) -> str:
        return f"{competition}_json.zip"

    def download_competition_zip(self, competition: str, destination: Path, force: bool = False) -> Path:
        """Download the zipped JSON archive for a competition."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not force:
            return destination

        url = f"{self.base_url}/{self.zip_filename(competition)}"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        destination.write_bytes(response.content)
        return destination

    def extract_zip(self, archive_path: Path, output_dir: Path, overwrite: bool = False) -> List[Path]:
        """Extract JSON files from a Cricsheet archive."""
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted: List[Path] = []
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.namelist():
                if not member.endswith(".json"):
                    continue
                target = output_dir / Path(member).name
                if target.exists() and not overwrite:
                    extracted.append(target)
                    continue
                with zf.open(member) as source, target.open("wb") as sink:
                    sink.write(source.read())
                extracted.append(target)
        return extracted

    def load_match_files(self, match_files: Iterable[Path]) -> pd.DataFrame:
        """Load multiple match JSON files into a single deliveries DataFrame."""
        frames: List[pd.DataFrame] = []
        for path in match_files:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            df = self.parse_match_json(data)
            df["match_id"] = data.get("info", {}).get("match_id", path.stem)
            df["season"] = data.get("info", {}).get("season")
            frames.append(df)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        return combined

    def parse_match_json(self, match_data: Dict) -> pd.DataFrame:
        rows: List[Dict] = []
        for innings in match_data.get("innings", []):
            innings_name = innings.get("team")
            for over in innings.get("overs", []):
                over_number = over.get("over")
                for delivery in over.get("deliveries", []):
                    rows.append(
                        {
                            "innings_team": innings_name,
                            "over": over_number,
                            "batter": delivery.get("batter"),
                            "non_striker": delivery.get("non_striker"),
                            "bowler": delivery.get("bowler"),
                            "runs_batter": delivery.get("runs", {}).get("batter", 0),
                            "runs_extras": delivery.get("runs", {}).get("extras", 0),
                            "runs_total": delivery.get("runs", {}).get("total", 0),
                            "wicket": 1 if delivery.get("wickets") else 0,
                            "wicket_detail": delivery.get("wickets"),
                        }
                    )
        return pd.DataFrame(rows)

    def load_from_bytes(self, payload: bytes) -> List[Dict]:
        """Return raw JSON dicts from an in-memory zip payload."""
        matches: List[Dict] = []
        with zipfile.ZipFile(BytesIO(payload)) as zf:
            for member in zf.namelist():
                if not member.endswith(".json"):
                    continue
                with zf.open(member) as source:
                    matches.append(json.load(source))
        return matches
