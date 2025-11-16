# 🎵 Mamlarr Metadata & Post-Processing Features

## Overview

Mamlarr now includes **professional-grade metadata extraction and audio processing** that makes downloaded audiobooks **AudiobookShelf-ready** with proper tags, cover art, and structured metadata.

## Features

### ✅ Metadata Extraction

**Extracts from MyAnonymouse payload:**
- **Title** - Book title
- **Authors** - Primary and additional authors
- **Narrators** - Voice actors/narrators
- **Series** - Series name and position
- **ASIN** - Amazon Standard Identification Number
- **Description** - Book description/synopsis
- **Cover URL** - Link to cover artwork
- **Publish Date** - Release date

**Smart Field Mapping:**
Handles various field name variations from different sources:
- `cover_url`, `coverUrl`, `image`, `image_url`, `thumbnail`, `poster`
- `author_info`, `authors` (JSON strings, lists, or dicts)
- `narrator_info`, `narrators`
- Gracefully falls back when fields are missing

### ✅ Filename Formatting

**"Author – Title" Format:**
```
Stephen King - The Stand.m4b
Andy Weir - Project Hail Mary.m4b
Terry Pratchett - Guards! Guards!.m4b
```

Benefits:
- Clean, readable filenames
- AudiobookShelf recognizes author automatically
- Consistent naming across library
- Special characters sanitized safely

### ✅ JSON Sidecar Files

**Creates `.metadata.json` for AudiobookShelf:**

```json
{
  "title": "Project Hail Mary",
  "authors": ["Andy Weir"],
  "narrators": ["Ray Porter"],
  "series": "Standalone",
  "asin": "B08G9PRS1K",
  "description": "A lone astronaut must save the earth from disaster...",
  "publishDate": "2021-05-04T00:00:00Z",
  "cover": "https://tracker.example/covers/12345.jpg"
}
```

**Placement:**
- Single file: `audiobook.m4b.metadata.json`
- Directory: `audiobook_dir/metadata.json`

AudiobookShelf reads these automatically for enhanced metadata display.

### ✅ Audio Metadata Embedding (ffmpeg)

**ID3/MP4 Tags Applied:**
- **Title** - Book title
- **Album** - Book title (for audio players)
- **Artist** - Narrator(s) or author(s)
- **Album Artist** - Primary author
- **Composer** - Narrator(s)
- **Comment** - Description

**Cover Art Embedding:**
- Downloads cover from tracker URL
- Embeds as album artwork in M4B/MP3
- Cached in temp directory
- Reused across retries

**Example ffmpeg command:**
```bash
ffmpeg -y -i input.m4b -i cover.jpg \
  -map 0:a -map 1:0 -c copy -disposition:v:0 attached_pic \
  -metadata title="Project Hail Mary" \
  -metadata album="Project Hail Mary" \
  -metadata artist="Ray Porter" \
  -metadata album_artist="Andy Weir" \
  -metadata composer="Ray Porter" \
  -metadata comment="Description..." \
  output.m4b
```

### ✅ Multi-File Merging

When audiobook has multiple files (chapters):
- Concatenates using ffmpeg
- Preserves audio quality (codec copy)
- Outputs single M4B file
- Applies metadata to merged result
- Embeds cover in final file

**Process:**
1. Gather all audio files (MP3, M4A, M4B, FLAC, etc.)
2. Create ffmpeg concat list
3. Merge with `-c copy` (no re-encoding)
4. Apply metadata tags
5. Embed cover art
6. Output to `Author - Title.m4b`

### ✅ AudiobookShelf Integration

**What AudiobookShelf Gets:**
```
/audiobooks/
├── Stephen_King_-_The_Stand.m4b           # Audio file with embedded metadata
├── Stephen_King_-_The_Stand.m4b.metadata.json  # Sidecar for enhanced display
├── Andy_Weir_-_Project_Hail_Mary.m4b
├── Andy_Weir_-_Project_Hail_Mary.m4b.metadata.json
└── Terry_Pratchett_-_Guards_Guards/
    ├── metadata.json                       # Directory-level metadata
    ├── chapter01.mp3                       # Individual chapters
    ├── chapter02.mp3
    └── cover.jpg                           # Downloaded cover
```

**AudiobookShelf Reads:**
- Title and author from filename (Author - Title format)
- Embedded audio tags (if M4B/MP3 with metadata)
- JSON sidecar for rich metadata (description, series, etc.)
- Embedded or separate cover image

Result: **Perfect library organization with full metadata!**

## Implementation Details

### Metadata Extraction (`_extract_metadata`)

```python
def _extract_metadata(self, job: DownloadJob) -> dict:
    source = job.source or {}      # Raw MAM payload
    release = job.release or {}    # Prowlarr-formatted data

    # Extract with fallbacks
    title = release.get("title") or source.get("title") or job.guid
    authors = self._parse_people(source, "author_info")
    narrators = self._parse_people(source, "narrator_info")

    # Build display name
    primary_author = authors[0] if authors else ""
    display_name = f"{primary_author} - {title}" if primary_author else title

    # Return structured metadata
    return {
        "title": title,
        "authors": authors,
        "narrators": narrators,
        "display_name": display_name,
        "ffmpeg_tags": {...},
        # ... more fields
    }
```

### People Parsing (`_parse_people`)

Handles various formats:
- **JSON string**: `'["Author One", "Author Two"]'`
- **List**: `["Author One", "Author Two"]`
- **Dict**: `{"1": "Author One", "2": "Author Two"}`
- **String**: `"Author Name"`

### Cover Download (`_download_cover`)

```python
async def _download_cover(self, cover_url: str) -> Optional[Path]:
    if not cover_url or not self.http_session:
        return None

    # Cache in temp directory
    cover_path = self.tmp_dir / f"cover_{hash(cover_url)}.jpg"

    if cover_path.exists():
        return cover_path  # Reuse cached

    # Download with shared aiohttp session
    async with self.http_session.get(cover_url) as response:
        if response.ok:
            cover_path.write_bytes(await response.read())
            return cover_path

    return None
```

### Metadata Application (`_apply_audio_metadata`)

```python
async def _apply_audio_metadata(self, file_path: Path, metadata: dict):
    tags = metadata.get("ffmpeg_tags") or {}
    cover_path = await self._download_cover(metadata.get("cover_url"))

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y", "-i", str(file_path)]

    if cover_path:
        cmd += ["-i", str(cover_path), "-map", "0:a", "-map", "1:0"]
        cmd += ["-c", "copy", "-disposition:v:0", "attached_pic"]
    else:
        cmd += ["-c", "copy"]

    # Add metadata tags
    for key, value in tags.items():
        if value:
            cmd += ["-metadata", f"{key}={value}"]

    # Execute
    await asyncio.create_subprocess_exec(*cmd)
```

## Configuration

### Enable/Disable Features

**Audio Merging:**
```bash
export MAM_SERVICE_ENABLE_AUDIO_MERGE="true"  # Merge multi-file audiobooks
```

**Requirements:**
- ffmpeg installed and in PATH
- Sufficient disk space for temporary files

### Mock Mode

Even in mock mode, metadata processing runs:
- Creates fake metadata
- Tests JSON sidecar creation
- Validates ffmpeg commands (if available)

## Benefits

### For Users
- ✅ **Clean Library** - Organized "Author - Title" format
- ✅ **Rich Metadata** - Full descriptions, series info
- ✅ **Cover Art** - Beautiful library display
- ✅ **Player Compatibility** - Works in any audio player
- ✅ **AudiobookShelf Ready** - Perfect integration

### For AudiobookShelf
- ✅ **Auto-Recognition** - Filename format parsed automatically
- ✅ **Enhanced Display** - Description, narrators, series
- ✅ **Cover Display** - Embedded or sidecar images
- ✅ **Search** - Metadata indexed for search

### For Organization
- ✅ **Consistent Naming** - All files follow same pattern
- ✅ **Self-Documenting** - Metadata travels with file
- ✅ **Portable** - Move files anywhere, metadata stays
- ✅ **Future-Proof** - Standard formats (JSON, ID3)

## Examples

### Single File Audiobook
**Input (from MAM):**
- File: `ProjectHailMary_Unabridged.m4b`
- Metadata: Author, narrator, cover in MAM payload

**Output:**
```
Andy_Weir_-_Project_Hail_Mary.m4b
Andy_Weir_-_Project_Hail_Mary.m4b.metadata.json
```

**Embedded in M4B:**
- Title: Project Hail Mary
- Artist: Ray Porter
- Album Artist: Andy Weir
- Cover: 1200x1200 JPEG

### Multi-File Audiobook
**Input (from MAM):**
```
The_Stand_Unabridged/
├── Part01.mp3
├── Part02.mp3
├── Part03.mp3
└── ...Part47.mp3
```

**Output:**
```
Stephen_King_-_The_Stand.m4b              # Merged single file
Stephen_King_-_The_Stand.m4b.metadata.json
```

### Directory-Based
**Input (from MAM):**
```
Guards_Guards/
├── 01-Prologue.mp3
├── 02-Chapter_1.mp3
└── ...
```

**Output:**
```
Terry_Pratchett_-_Guards_Guards/
├── metadata.json
├── 01-Prologue.mp3
├── 02-Chapter_1.mp3
└── ...
```

## Troubleshooting

### Cover not downloading
- Check internet connection
- Verify cover URL is accessible
- Check temp directory permissions

### ffmpeg not applying tags
- Verify ffmpeg is installed: `which ffmpeg`
- Check ffmpeg supports format: `ffmpeg -formats`
- Look at logs for ffmpeg errors

### Metadata file not created
- Check output directory permissions
- Verify metadata extraction succeeded
- Look for `title` field in job source

### Author not in filename
- MAM payload must include author info
- Check `author_info` or `authors` fields
- Falls back to title only if author missing

## Future Enhancements

### Planned
- [ ] ChapterDB.org integration for chapter markers
- [ ] Multiple cover sizes (thumbnail + full)
- [ ] Series auto-detection from title
- [ ] ASIN-based Audible metadata fetch
- [ ] M4B chapter markers from file boundaries

### Nice to Have
- [ ] Manual metadata editing in UI
- [ ] Bulk metadata refresh
- [ ] Custom filename templates
- [ ] Metadata validation/cleanup

## Testing

### Test Metadata Extraction
```bash
# Start in mock mode
./run_dev_server.sh

# Download will create:
output/
├── mock_book_1.m4b
└── mock_book_1.m4b.metadata.json
```

### Verify JSON Sidecar
```bash
cat output/*.metadata.json
# Should show title, authors, etc.
```

### Check Embedded Metadata
```bash
ffprobe output/*.m4b 2>&1 | grep -A 10 "Metadata:"
# Should show title, artist, album, etc.
```

## Summary

Mamlarr's metadata features transform raw tracker downloads into **professionally tagged audiobooks** ready for AudiobookShelf or any audio player.

**Key Features:**
- ✅ Automatic metadata extraction from MAM
- ✅ "Author - Title" filename formatting
- ✅ JSON sidecar for AudiobookShelf
- ✅ Embedded audio tags (ID3/MP4)
- ✅ Cover art downloading and embedding
- ✅ Multi-file merging with metadata preservation

**Result:** A clean, organized audiobook library with full metadata! 🎵
