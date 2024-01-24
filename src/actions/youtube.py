import subprocess
import os
import sys
import logging
import re
import threading

from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stderr))


def extract_youtube_link_and_id(message):
    # Regular expression pattern to find YouTube URLs
    youtube_url_pattern = (
        r"(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w\-]+)"
    )
    # Search for the pattern in the message
    match = re.search(youtube_url_pattern, message)
    # If a match is found, extract the URL and the 'v' parameter
    if match:
        url = match.group()
        # Parsing the URL to extract the 'v' parameter
        parsed_url = urlparse(url)
        # For 'youtube.com' links, the video ID is stored in query parameters
        if "youtube.com" in parsed_url.netloc:
            video_id = parse_qs(parsed_url.query).get("v", [None])[0]
        # For 'youtu.be' links, the video ID is stored in the path
        else:
            video_id = parsed_url.path[1:]
        return url, video_id
    else:
        return None, None

class PlayYoutube:
    def __init__(self):
        pass

    def run(self, message: str, queue):
        url, v_id = extract_youtube_link_and_id(message)
        if url:
            logger.info('processing "%s"', url)

            output = subprocess.check_output(
                ["yt-dlp", "--list-formats", url], encoding="utf8"
            )
            for line in output.splitlines():
                if "audio only" in line:
                    y_format = line.split()[0]
                    logger.debug('Format string "%s", format %s', line, y_format)
                    p = subprocess.run(
                        ["yt-dlp", "-f", y_format, "-g", url],
                        encoding="utf8",
                        stdout=subprocess.PIPE,
                    )
                    if p.stdout.startswith("https://"):
                        url = p.stdout.strip()
                        break
                    else:
                        logger.warning("failed to get the url of the stream: %s", p.stdout)
            else:
                raise Exception("Audio-only stream is not found")

            cmd = ["cvlc", "--play-and-exit", url]
            logger.info('playing "%s"', cmd)
            
            p = subprocess.Popen(cmd)
            
            def event_listener():
                while True:
                    command = queue.down.get()  # Get a command from the queue
                    logger.debug("received command: %s", command)
                    if command == "STOP":
                        p.terminate()
                        p.kill()
                    
                    break

            def play():
                p.wait()
                queue.up.put("FINISHED")
  
            threading.Thread(target=play).start()
            threading.Thread(target=event_listener).start()
            return True
        else:
            return False