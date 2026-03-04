import xml.etree.ElementTree as ET
import logging
import re
import requests
import json
from urllib.parse import urlparse, parse_qs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

INPUT_XML = "youtubelinks.xml"
OUTPUT_M3U = "youtube_output.m3u"


# ------------------------------------------------------------
# Parse XML
# ------------------------------------------------------------
def parse_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    channels = []
    for ch in root.findall("channel"):
        channels.append({
            "name": ch.findtext("channel-name", "").strip(),
            "tvg-id": ch.findtext("tvg-id", "").strip(),
            "tvg-name": ch.findtext("tvg-name", "").strip(),
            "tvg-logo": ch.findtext("tvg-logo", "").strip(),
            "group-title": ch.findtext("group-title", "General").strip(),
            "youtube-url": ch.findtext("youtube-url", "").strip(),
        })
    return channels


# ------------------------------------------------------------
# Normalize URL formats
# ------------------------------------------------------------
def normalize_url(url):
    parsed = urlparse(url)

    if parsed.netloc.startswith("m."):
        url = url.replace("m.youtube.com", "www.youtube.com")

    if parsed.netloc == "youtu.be":
        vid = parsed.path.strip("/")
        if len(vid) == 11:
            return f"https://www.youtube.com/watch?v={vid}"

    m = re.match(r"^/shorts/([\w-]{11})", parsed.path)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"

    m = re.match(r"^/embed/([\w-]{11})", parsed.path)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"

    return url


# ------------------------------------------------------------
# Recursive search in ytInitialData
# ------------------------------------------------------------
def search_video_id(data):
    if isinstance(data, dict):
        if "videoRenderer" in data:
            vr = data["videoRenderer"]
            if "videoId" in vr:
                return vr["videoId"]
        for v in data.values():
            r = search_video_id(v)
            if r:
                return r
    elif isinstance(data, list):
        for item in data:
            r = search_video_id(item)
            if r:
                return r
    return None


# ------------------------------------------------------------
# Extract Video ID (consent bypass regex fixed)
# ------------------------------------------------------------
def get_video_id(session, url):

    url = normalize_url(url)
    parsed = urlparse(url)

    # Direct watch?v= format
    if parsed.path == "/watch":
        qs = parse_qs(parsed.query)
        if "v" in qs:
            logging.info("Video ID extracted from watch URL")
            return qs["v"][0]

    # /live/VIDEOID format
    m = re.match(r"^/live/([\w-]{11})", parsed.path)
    if m:
        logging.info("Video ID extracted from /live/ path")
        return m.group(1)

    logging.info(f"Fetching page: {url}")

    try:
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        logging.error(f"Fetch failed: {e}")
        return None

    html = r.text
    final_url = r.url

    # Detect and bypass consent page
    if "consent.youtube.com" in final_url or "Manage your YouTube cookies" in html or "CONSENT" in html.upper():
        logging.info("Detected consent page - attempting to bypass")

        # FIXED regex: safer capture to avoid unbalanced paren issues
        accept_match = re.search(
            r'href\s*=\s*"([^"]*consent\.youtube\.com/save\?[^"]*)"',
            html,
            re.IGNORECASE | re.DOTALL
        )
        if accept_match:
            accept_url = accept_match.group(1)
            logging.info(f"Following consent accept link: {accept_url}")
            try:
                r = session.get(accept_url, timeout=20, allow_redirects=True)
                html = r.text
                final_url = r.url
                logging.info(f"After consent bypass, landed at: {final_url}")
            except Exception as e:
                logging.warning(f"Consent accept follow failed: {e}")
        else:
            # Fallback: set common consent cookies manually
            logging.info("No accept link found - setting consent cookies manually")
            session.cookies.set(
                "SOCS", "CAESEwgDEgk0MjAxMjA3MTEaAmVuIAEaBgiA_7GfBg",
                domain=".youtube.com", path="/"
            )
            session.cookies.set(
                "CONSENT", "YES+srp.gws-20211028-0-RC1.en+FX+123",
                domain=".youtube.com", path="/"
            )
            # Retry original URL with cookies
            try:
                r = session.get(url, timeout=20, allow_redirects=True)
                html = r.text
                final_url = r.url
                logging.info(f"After setting cookies, final URL: {final_url}")
            except Exception as e:
                logging.warning(f"Retry after cookie set failed: {e}")

    # Now try to extract video ID from (hopefully) real page
    # 1. Canonical link (best for /@handle/live pages)
    m_canonical = re.search(
        r'<link\s+rel=["\']canonical["\']\s+href=["\']https?://(?:www\.)?youtube\.com/watch\?v=([\w-]{11})["\']',
        html,
        re.IGNORECASE
    )
    if m_canonical:
        vid = m_canonical.group(1)
        logging.info("Video ID extracted from canonical <link> tag")
        return vid

    # 2. og:url meta tag fallback
    m_og = re.search(
        r'<meta\s+property=["\']og:url["\']\s+content=["\'](.*?)["\']',
        html,
        re.IGNORECASE | re.DOTALL
    )
    if m_og:
        og_url = m_og.group(1)
        parsed_og = urlparse(og_url)
        qs = parse_qs(parsed_og.query)
        if "v" in qs and len(qs["v"][0]) == 11:
            vid = qs["v"][0]
            logging.info("Video ID extracted from og:url meta tag")
            return vid

    # 3. Strong global search for videoId
    match = re.search(r'"videoId"\s*:\s*"([\w-]{11})"', html)
    if match:
        logging.info("Video ID extracted from page source (videoId JSON)")
        return match.group(1)

    # 4. ytInitialData fallback
    match = re.search(
        r'var\s+ytInitialData\s*=\s*({.*?})\s*;\s*</script>',
        html,
        re.DOTALL
    )
    if match:
        try:
            data = json.loads(match.group(1))
            vid = search_video_id(data)
            if vid:
                logging.info("Video ID extracted from ytInitialData")
                return vid
        except Exception:
            pass

    # 5. Check if finally redirected to /watch
    if final_url != url:
        logging.info(f"Final page is: {final_url}")
        parsed_final = urlparse(final_url)
        if parsed_final.path == "/watch":
            qs = parse_qs(parsed_final.query)
            if "v" in qs:
                logging.info("Video ID extracted from final redirected watch URL")
                return qs["v"][0]

    logging.warning("No video ID found after all attempts")
    return None


# ------------------------------------------------------------
# Extract visitorData
# ------------------------------------------------------------
def get_visitor_data(html):
    m = re.search(r'"visitorData"\s*:\s*"([^"]+)"', html)
    return m.group(1) if m else None


# ------------------------------------------------------------
# Extract HLS via InnerTube
# ------------------------------------------------------------
def extract_youtube_stream(youtube_url):

    session = requests.Session()

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    video_id = get_video_id(session, youtube_url)
    if not video_id:
        logging.error("Could not resolve video ID")
        return None

    logging.info(f"Final video ID: {video_id}")

    # Fetch watch page with same session (cookies preserved)
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    watch_html = session.get(watch_url, timeout=20).text

    api_key_match = re.search(
        r'"INNERTUBE_API_KEY":"([^"]+)"',
        watch_html
    )
    if not api_key_match:
        logging.error("Could not find INNERTUBE_API_KEY")
        return None
    api_key = api_key_match.group(1)

    visitor_data = get_visitor_data(watch_html)

    player_url = f"https://www.youtube.com/youtubei/v1/player?key={api_key}&prettyPrint=false"

    clients = [
        {"clientName": "ANDROID_VR", "clientVersion": "1.60.19"},
        {"clientName": "ANDROID", "clientVersion": "20.10.38"},
        {"clientName": "WEB_EMBEDDED_PLAYER", "clientVersion": "2.20260301.00.00"},
    ]

    for client in clients:
        logging.info(f"Trying client: {client['clientName']}")

        payload = {
            "videoId": video_id,
            "contentCheckOk": True,
            "racyCheckOk": True,
            "context": {
                "client": client,
                "user": {"lockedSafetyMode": False}
            }
        }

        if visitor_data:
            payload["context"]["client"]["visitorData"] = visitor_data

        try:
            r = session.post(player_url, json=payload, timeout=25)
            r.raise_for_status()
            data = r.json()

            hls = data.get("streamingData", {}).get("hlsManifestUrl")
            if hls:
                logging.info(f"Success! HLS URL from {client['clientName']}")
                return hls

        except Exception as e:
            logging.debug(f"Client {client['clientName']} failed: {e}")
            continue

    logging.error("All clients failed to get HLS URL")
    return None


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():

    channels = parse_xml(INPUT_XML)

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:

        f.write("#EXTM3U\n")

        for ch in channels:

            logging.info(f"--- Processing: {ch['name']} ({ch['youtube-url']}) ---")

            hls = extract_youtube_stream(ch["youtube-url"])

            if not hls:
                logging.warning("Skipping channel")
                continue

            f.write(
                f'#EXTINF:-1 tvg-id="{ch["tvg-id"]}" '
                f'tvg-name="{ch["tvg-name"]}" '
                f'tvg-logo="{ch["tvg-logo"]}" '
                f'group-title="{ch["group-title"]}",'
                f'{ch["name"]}\n'
            )
            f.write(f"{hls}\n\n")

            logging.info("Added to playlist")

    logging.info(f"Playlist written: {OUTPUT_M3U}")


if __name__ == "__main__":
    main()