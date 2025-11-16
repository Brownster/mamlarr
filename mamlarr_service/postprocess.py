from __future__ import annotations

import asyncio
import os
import shutil
import json
from pathlib import Path
from typing import Iterable, List, Optional

from aiohttp import ClientSession

from .log import logger

from .models import DownloadJob

AUDIO_EXTENSIONS = {".mp3", ".m4b", ".m4a", ".flac", ".aac", ".ogg", ".wav", ".opus"}


class PostProcessingError(RuntimeError):
    pass


def _sanitize_name(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_"))
    safe = safe.strip().replace(" ", "_")
    return safe or "audiobook"


class PostProcessor:
    def __init__(
        self,
        output_dir: Path,
        tmp_dir: Path,
        enable_merge: bool = True,
        http_session: Optional[ClientSession] = None,
    ):
        self.output_dir = output_dir
        self.tmp_dir = tmp_dir
        self.enable_merge = enable_merge
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.http_session = http_session

    async def process(self, job: DownloadJob, torrent: dict) -> Path:
        download_dir = Path(torrent.get("downloadDir", ""))
        metadata = self._extract_metadata(job)
        display_name = metadata.get("display_name") or torrent.get("name")
        name = display_name or job.release.get("title") or job.guid
        source_path = download_dir / name
        if not source_path.exists():
            raise PostProcessingError(f"Source path does not exist: {source_path}")
        files = torrent.get("files", [])
        audio_files = self._gather_audio_files(download_dir, files)
        dest_name = _sanitize_name(name)
        destination = self.output_dir / dest_name
        if destination.exists():
            destination = self.output_dir / f"{dest_name}_{job.id[:8]}"

        if not audio_files:
            # no audio metadata, copy entire folder/file
            await asyncio.to_thread(self._copy_any, source_path, destination)
            return destination

        if len(audio_files) == 1:
            destination = destination.with_suffix(audio_files[0].suffix.lower())
            await asyncio.to_thread(self._copy_file, audio_files[0], destination)
            await self._finalize_metadata(destination, metadata)
            return destination

        if self.enable_merge and self.ffmpeg_path:
            merged = destination.with_suffix(".m4b")
            merged.parent.mkdir(parents=True, exist_ok=True)
            await self._merge_with_ffmpeg(audio_files, merged)
            await self._finalize_metadata(merged, metadata)
            return merged

        # fallback: copy directory containing files
        await asyncio.to_thread(self._copy_any, source_path, destination)
        await self._finalize_metadata(destination, metadata)
        return destination

    def _gather_audio_files(self, base_dir: Path, files: Iterable[dict]) -> List[Path]:
        audio_paths: List[Path] = []
        for f in files:
            name = f.get("name")
            if not isinstance(name, str):
                continue
            path = base_dir / name
            if path.suffix.lower() in AUDIO_EXTENSIONS and path.exists():
                audio_paths.append(path)
        audio_paths.sort()
        return audio_paths

    async def _merge_with_ffmpeg(self, files: List[Path], destination: Path) -> None:
        list_file_path = self.tmp_dir / f"ffmpeg_concat_{os.getpid()}_{destination.stem}.txt"
        with list_file_path.open("w", encoding="utf-8") as fh:
            for file in files:
                fh.write(f"file '{file.as_posix()}'\n")

        cmd = [
            self.ffmpeg_path,
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file_path),
            "-c",
            "copy",
            str(destination),
        ]
        logger.info("PostProcessor: merging audio with ffmpeg", output=str(destination))
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        list_file_path.unlink(missing_ok=True)
        if process.returncode != 0:
            raise PostProcessingError(
                f"ffmpeg failed ({process.returncode}): {stderr.decode() or stdout.decode()}"
            )

    def _copy_any(self, source: Path, destination: Path) -> None:
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def _copy_file(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    async def _finalize_metadata(self, destination: Path, metadata: dict) -> None:
        await self._write_metadata_file(destination, metadata)
        if destination.is_file():
            await self._apply_audio_metadata(destination, metadata)

    def _extract_metadata(self, job: DownloadJob) -> dict:
        source = job.source or {}
        release = job.release or {}
        title = release.get("title") or source.get("title") or job.guid
        authors = self._parse_people(source, "author_info") or source.get("authors") or []
        narrators = self._parse_people(source, "narrator_info") or source.get("narrators") or []
        if isinstance(authors, str):
            authors = [authors]
        if isinstance(narrators, str):
            narrators = [narrators]
        series = source.get("series") or release.get("series")
        asin = source.get("asin") or release.get("asin")
        description = source.get("description") or source.get("desc")
        cover_url = (
            source.get("cover_url")
            or source.get("coverUrl")
            or source.get("image")
            or source.get("image_url")
            or source.get("thumbnail")
            or source.get("poster")
        )
        primary_author = authors[0] if authors else ""
        display_name = f"{primary_author} - {title}" if primary_author else title

        ffmpeg_tags = {
            "title": title,
            "album": title,
            "artist": ", ".join(narrators or authors),
            "album_artist": primary_author or ", ".join(authors),
            "composer": ", ".join(narrators) if narrators else None,
            "comment": description,
        }
        return {
            "title": title,
            "authors": authors,
            "narrators": narrators,
            "series": series,
            "asin": asin,
            "description": description,
            "cover_url": cover_url,
            "publish_date": release.get("publishDate"),
            "ffmpeg_tags": ffmpeg_tags,
            "display_name": display_name,
        }

    def _parse_people(self, data: dict, key: str) -> list[str]:
        value = data.get(key)
        if not value:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, (str, int))]
        if isinstance(value, dict):
            return [str(v) for v in value.values() if v]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed if v]
                if isinstance(parsed, dict):
                    return [str(v) for v in parsed.values() if v]
            except Exception:
                pass
            return [value]
        return []

    async def _write_metadata_file(self, destination: Path, metadata: dict) -> None:
        if not metadata.get("title"):
            return
        payload = {
            "title": metadata.get("title"),
            "authors": metadata.get("authors"),
            "narrators": metadata.get("narrators"),
            "series": metadata.get("series"),
            "asin": metadata.get("asin"),
            "description": metadata.get("description"),
            "publishDate": metadata.get("publish_date"),
            "cover": metadata.get("cover_url"),
        }
        if destination.is_dir():
            meta_path = destination / "metadata.json"
        else:
            meta_path = destination.with_suffix(destination.suffix + ".metadata.json")
        meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    async def _apply_audio_metadata(self, file_path: Path, metadata: dict) -> None:
        if not self.ffmpeg_path or not file_path.exists():
            return
        tags = metadata.get("ffmpeg_tags") or {}
        cover_path = await self._download_cover(metadata.get("cover_url"))
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        cmd = [self.ffmpeg_path, "-y", "-i", str(file_path)]
        if cover_path:
            cmd += [
                "-i",
                str(cover_path),
                "-map",
                "0",
                "-map",
                "1",
                "-c",
                "copy",
                "-metadata:s:v",
                "title=Cover",
                "-metadata:s:v",
                "comment=Cover (front)",
                "-disposition:v",
                "attached_pic",
            ]
        else:
            cmd += ["-c", "copy"]
        for key, value in tags.items():
            if value:
                cmd += ["-metadata", f"{key}={value}"]
        cmd.append(str(temp_path))
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if cover_path:
            cover_path.unlink(missing_ok=True)
        if process.returncode != 0:
            temp_path.unlink(missing_ok=True)
            logger.error(
                "PostProcessor: failed to apply metadata",
                error=stderr.decode() or stdout.decode(),
            )
            return
        file_path.unlink(missing_ok=True)
        temp_path.rename(file_path)

    async def _download_cover(self, url: Optional[str]) -> Optional[Path]:
        if not url or not self.http_session:
            return None
        try:
            async with self.http_session.get(url) as resp:
                if not resp.ok:
                    return None
                data = await resp.read()
        except Exception as exc:
            logger.debug("PostProcessor: cover fetch failed", error=str(exc))
            return None
        cover_path = self.tmp_dir / f"cover_{os.getpid()}.jpg"
        cover_path.write_bytes(data)
        return cover_path
