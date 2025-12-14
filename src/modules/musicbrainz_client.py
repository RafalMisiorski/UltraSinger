import musicbrainzngs
import string
import time
import urllib.error
from Levenshtein import ratio
from dataclasses import dataclass
from typing import Optional
from Settings import Settings

from modules.console_colors import ULTRASINGER_HEAD, blue_highlighted, red_highlighted, safe_print

# Retry configuration for network errors
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds, will be multiplied by attempt number


@dataclass
class SongInfo:
    title: str
    artist: str
    year: Optional[str] = None
    genres: Optional[str] = None
    cover_image_data: Optional[bytes] = None
    cover_url: Optional[str] = None


title_filter = [
    "official video",
    "official music video",
    "Offizielles Musikvideo",
    "sanremo 2025",
    "sanremo 2024",
    "sanremo 2023",
]


def extract_artist_and_title_from_string(origin_title: str) -> tuple[str, str]:
    """
    Try to extract artist and title from a YouTube-style title string.
    Common patterns: "Artist - Song", "Artist_-_Song", "Artist - Song (Official Video)"
    Returns (artist, title) or (None, origin_title) if extraction fails.
    """
    import re

    # Clean up the title first
    cleaned = origin_title
    for f in title_filter:
        cleaned = re.sub(re.escape(f), '', cleaned, flags=re.IGNORECASE).strip()

    # Remove common suffixes in parentheses or brackets
    cleaned = re.sub(r'\s*[\(\[].*?[\)\]]', '', cleaned).strip()

    # Try different separator patterns
    separators = [
        r'\s+[-–—]\s+',      # "Artist - Song" with various dash types
        r'_-_',              # "Artist_-_Song" (YouTube style)
        r'\s*[-–—]\s*',      # "Artist-Song" with less strict spacing
    ]

    for sep in separators:
        parts = re.split(sep, cleaned, maxsplit=1)
        if len(parts) == 2:
            artist = parts[0].strip().replace('_', ' ')
            title = parts[1].strip().replace('_', ' ')
            # Clean up any trailing/leading underscores or spaces
            artist = re.sub(r'^[_\s]+|[_\s]+$', '', artist)
            title = re.sub(r'^[_\s]+|[_\s]+$', '', title)
            if artist and title:
                return artist, title

    return None, origin_title


def __clean_string(s: str) -> str:
    return s.translate(str.maketrans('', '', string.punctuation)).lower().strip()


def search_musicbrainz(title: str, artist) -> SongInfo:
    # Musicbrainz API documentation
    # https://python-musicbrainzngs.readthedocs.io/en/latest/api/

    musicbrainzngs.set_useragent("UltraSinger", Settings.APP_VERSION, "https://github.com/rakuri255/UltraSinger")

    # remove from search_string "official video"
    # todo: do we need filter?
    origin_title = title
    for filter in title_filter:
        title = title.lower().replace(filter.lower(), "").strip()
        if artist is not None:
            artist = artist.lower().replace(filter.lower(), "").strip()

    # Retry logic for network errors
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if artist is None:
                recording = __single_line_search(title)
            else:
                recording = __multi_line_search(artist, title)
            break  # Success, exit retry loop
        except (urllib.error.URLError, ConnectionResetError, OSError, musicbrainzngs.NetworkError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY_BASE * attempt
                print(f"{ULTRASINGER_HEAD} {red_highlighted(f'Network error (attempt {attempt}/{MAX_RETRIES}): {e}')}")
                print(f"{ULTRASINGER_HEAD} Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"{ULTRASINGER_HEAD} {red_highlighted(f'Failed after {MAX_RETRIES} attempts: {e}')}")
                raise  # Re-raise after all retries exhausted

    if recording is None:
        print(f"{ULTRASINGER_HEAD} {red_highlighted('No match found on MusicBrainz')}")
        # Try to extract artist from the title string (YouTube-style: "Artist - Song")
        extracted_artist, extracted_title = extract_artist_and_title_from_string(origin_title)
        if extracted_artist:
            safe_print(f"{ULTRASINGER_HEAD} Extracted from title: Artist={blue_highlighted(extracted_artist)} Title={blue_highlighted(extracted_title)}")
            return SongInfo(title=extracted_title, artist=extracted_artist)
        else:
            print(f"{ULTRASINGER_HEAD} {red_highlighted('Could not extract artist from title, using Unknown Artist')}")
            return SongInfo(title=origin_title, artist="Unknown Artist")

    artist = recording['artist-credit-phrase']
    title = recording['title']
    safe_print(
        f"{ULTRASINGER_HEAD} Found data on Musicbrainz: Artist={blue_highlighted(artist)} Title={blue_highlighted(title)}")

    year = __get_year(recording)
    genres = __get_genres(recording)
    image_data, image_url = __get_image(recording)

    return SongInfo(title=title, artist=artist, year=year, genres=genres, cover_image_data=image_data, cover_url=image_url)


def __single_line_search(search_string):
    search_string = __clean_string(search_string)
    search_string = __filter_words(search_string)

    artists = musicbrainzngs.search_artists(search_string, limit=10, artist=search_string)
    recordings = musicbrainzngs.search_recordings(search_string, limit=100, artistname=search_string)
    found_artist = None

    for record in recordings['recording-list']:
        if found_artist is not None:
            break

        for artist_credit in record['artist-credit']:
            if found_artist is not None:
                break
            if isinstance(artist_credit, str):
                continue
            # todo: there is also an "alias-list". Maybe search also there?

            for artist in artists['artist-list']:
                if artist_credit['artist'] and artist_credit['artist']['id'] == artist['id']:
                    found_artist = record['artist-credit-phrase']
                    break

    if found_artist is None:
        return None

    recordings = [x for x in recordings['recording-list'] if
                  __clean_string(x['artist-credit-phrase']) == __clean_string(found_artist)]

    recording = None

    for record in recordings:
        if __clean_string(record['title']) in __clean_string(search_string):
            recording = record

    return recording


def __filter_words(search_string):
    for filter in title_filter:
        search_string = search_string.lower().replace(filter.lower(), "").strip()
    return search_string


def __multi_line_search(artist: str, title: str):
    # Try both combinations since we don't know which one is the artist and which one is the title
    artist1, title1 = artist, title
    artist2, title2 = title, artist

    result1 = musicbrainzngs.search_recordings(recording=title1, limit=10, artist=artist1, artistname=artist1)
    result2 = musicbrainzngs.search_recordings(recording=title2, limit=10, artist=artist2, artistname=artist2)

    # Filter result to ['artist-credit-phrase'] == artist
    record1 = [x for x in result1['recording-list'] if
               __clean_string(x['artist-credit-phrase']) == __clean_string(artist1)]
    record2 = [x for x in result2['recording-list'] if
               __clean_string(x['artist-credit-phrase']) == __clean_string(artist2)]

    if len(record1) > 0 and len(record2) > 0:
        best_match1 = max(record1, key=lambda x: ratio(__clean_string(x['title']), __clean_string(title1)))
        best_match2 = max(record2, key=lambda x: ratio(__clean_string(x['title']), __clean_string(title2)))

        is_match1 = ratio(__clean_string(title1), __clean_string(best_match1['title'])) > ratio(__clean_string(title2),
                                                                                                __clean_string(
                                                                                                    best_match2[
                                                                                                        'title']))

        if is_match1:
            recording = record1[0]
        else:
            recording = record2[0]

    elif len(record1) > 0:
        recording = record1[0]
    elif len(record2) > 0:
        recording = record2[0]
    elif result1['recording-count'] > 0:  # Artist = Title
        recording = result1['recording-list'][0]
    elif result2['recording-count'] > 0:  # Artist = Title
        recording = result2['recording-list'][0]
    else:
        recording = None

    return recording


def __get_image(recording) -> (bytes, str):
    image_data = None
    image_url = None
    if 'release-list' in recording:
        for release in recording['release-list']:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    image_data = musicbrainzngs.get_image_front(release['id'])
                    image_list = musicbrainzngs.get_image_list(release['id'])
                    for image in image_list['images']:
                        if image['front']:
                            image_url = image['image']
                            break
                    break  # Success, exit retry loop
                except (urllib.error.URLError, ConnectionResetError, OSError, musicbrainzngs.NetworkError) as e:
                    if attempt < MAX_RETRIES:
                        delay = RETRY_DELAY_BASE * attempt
                        print(f"{ULTRASINGER_HEAD} {red_highlighted(f'Network error getting image (attempt {attempt}/{MAX_RETRIES}): {e}')}")
                        time.sleep(delay)
                    else:
                        # After all retries, continue to next release
                        break
                except musicbrainzngs.ResponseError:
                    break  # No image for this release, try next
            if image_data is not None:
                break  # Found image, exit release loop
    if image_data is not None:
        print(f"{ULTRASINGER_HEAD} Found cover image")

    return image_data, image_url


def __get_year(recording):
    year = None

    if 'release-list' not in recording:
        return year

    release_group_id = recording['release-list'][0]['release-group']['id']

    # Retry logic for network errors
    release_group = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            release_group = musicbrainzngs.get_release_group_by_id(release_group_id)
            break  # Success, exit retry loop
        except (urllib.error.URLError, ConnectionResetError, OSError, musicbrainzngs.NetworkError) as e:
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY_BASE * attempt
                print(f"{ULTRASINGER_HEAD} {red_highlighted(f'Network error getting year (attempt {attempt}/{MAX_RETRIES}): {e}')}")
                time.sleep(delay)
            else:
                print(f"{ULTRASINGER_HEAD} {red_highlighted(f'Failed to get year after {MAX_RETRIES} attempts')}")
                return year  # Return None instead of crashing

    if release_group is None:
        return year

    if 'first-release-date' not in release_group['release-group']:
        return year

    year = release_group['release-group']['first-release-date'].strip()
    year = year.split('-')[0]

    if year is not None:
        print(f"{ULTRASINGER_HEAD} Found year: {blue_highlighted(year)}")

    return year


def __get_genres(recording) -> str:
    # todo secondary-type-list ??
    genres = None
    if 'tag-list' in recording:
        genres = ""
        for tag in recording['tag-list']:
            genres += f"{tag['name'].strip()},"
    if genres is not None:
        safe_print(f"{ULTRASINGER_HEAD} Found genres: {blue_highlighted(genres)}")
    return genres
