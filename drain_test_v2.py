import os
import sys
import json
import re
from collections import defaultdict

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig


# ==========================================================
# USAGE
#
# python3 drain_test_v2.py C:\path\to\logs
# ==========================================================

if len(sys.argv) < 2:
    print("Usage: python3 drain_test_v2.py FOLDER")
    sys.exit(1)

ROOT = os.path.abspath(sys.argv[1])

OUTPUT_FILE = os.path.join(
    ROOT,
    "drain_templates_v2.json"
)


# ==========================================================
# FILE TYPES TO SKIP
# ==========================================================

SKIP_EXTENSIONS = {
    ".exe", ".dll", ".so", ".sys",
    ".jpg", ".jpeg", ".png", ".gif",
    ".bmp", ".ico",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov",
    ".zip", ".rar", ".7z", ".gz", ".tar",
    ".iso", ".bin", ".pdf",
}


# ==========================================================
# PRE-COMPILED REGEX
# ==========================================================

# 2026-07-15 18:29:21.250
TIMESTAMP_1 = re.compile(
    r"\b\d{4}-\d{2}-\d{2}"
    r"[ T]"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:[.,]\d+)?\b"
)

# 04.02,2026.346 style seen in your logs
TIMESTAMP_2 = re.compile(
    r"\b\d{2}\.\d{2},\d{4}\.\d+\b"
)

# 2026-07-15
DATE_1 = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
)

# 04/18/2026 etc.
DATE_2 = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b"
)

# 18:29:21.250
TIME_1 = re.compile(
    r"\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b"
)

# IPv4
IPV4 = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
)

# MAC address
MAC = re.compile(
    r"\b(?:[0-9A-Fa-f]{2}[:-]){5}"
    r"[0-9A-Fa-f]{2}\b"
)

# Hex values such as 0x03, 0xFF
HEX_VALUE = re.compile(
    r"\b0x[0-9A-Fa-f]+\b"
)


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_message(text):
    """
    Remove obvious dynamic noise before sending
    the message to Drain3.

    IMPORTANT:
    We intentionally do NOT replace every number.
    """

    text = TIMESTAMP_1.sub("<TIMESTAMP>", text)
    text = TIMESTAMP_2.sub("<TIMESTAMP>", text)

    text = DATE_1.sub("<DATE>", text)
    text = DATE_2.sub("<DATE>", text)

    text = TIME_1.sub("<TIME>", text)

    text = IPV4.sub("<IP>", text)
    text = MAC.sub("<MAC>", text)
    text = HEX_VALUE.sub("<HEX>", text)

    # Remove NUL characters
    text = text.replace("\x00", "")

    # Normalize excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


# ==========================================================
# SPLIT ONE PHYSICAL LINE INTO LOGICAL EVENTS
# ==========================================================

def split_logical_messages(raw_line):
    """
    Some files contain literal backslash+n:

        event1\\nevent2\\nevent3

    Python's normal line iterator sees that as ONE line.

    This function splits those into separate messages.
    """

    # Remove real newline from end of physical line
    raw_line = raw_line.rstrip("\r\n")

    if not raw_line:
        return []

    # Split literal:
    #
    # \n
    # \r\n
    #
    # stored as characters inside the text.
    parts = re.split(
        r"\\r\\n|\\n|\\r",
        raw_line
    )

    result = []

    for part in parts:

        part = part.strip()

        if not part:
            continue

        normalized = normalize_message(part)

        if normalized:
            result.append(normalized)

    return result


# ==========================================================
# DRAIN3
# ==========================================================

config = TemplateMinerConfig()

config.profiling_enabled = False

config.drain_depth = 4
config.drain_sim_th = 0.4

template_miner = TemplateMiner(
    persistence_handler=None,
    config=config
)


# ==========================================================
# STATISTICS
# ==========================================================

file_templates = defaultdict(
    lambda: defaultdict(int)
)

total_files = 0

# Physical lines read from files
physical_lines = 0

# Logical events actually sent to Drain3
logical_events = 0

# Number of physical lines that contained literal \n
embedded_newline_lines = 0


# ==========================================================
# FILE FILTER
# ==========================================================

def should_skip(filename):

    lower_name = filename.lower()

    extension = os.path.splitext(
        lower_name
    )[1]

    if extension in SKIP_EXTENSIONS:
        return True

    if lower_name in {
        "drain_templates.json",
        "drain_templates_v2.json"
    }:
        return True

    return False


# ==========================================================
# PROCESS FILE
# ==========================================================

def process_file(file_path, relative_path):

    global physical_lines
    global logical_events
    global embedded_newline_lines

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for raw_line in f:

                physical_lines += 1

                # Detect literal backslash+n
                if (
                    "\\n" in raw_line
                    or "\\r" in raw_line
                ):
                    embedded_newline_lines += 1

                messages = split_logical_messages(
                    raw_line
                )

                for message in messages:

                    logical_events += 1

                    result = (
                        template_miner
                        .add_log_message(message)
                    )

                    cluster_id = result[
                        "cluster_id"
                    ]

                    file_templates[
                        relative_path
                    ][cluster_id] += 1


                    if logical_events % 100000 == 0:

                        print(
                            f"Events processed: "
                            f"{logical_events:,} | "
                            f"Templates: "
                            f"{len(template_miner.drain.clusters):,}",
                            flush=True
                        )

    except (PermissionError, OSError) as error:

        print(
            f"Cannot read: {relative_path}"
        )

        print(
            f"Reason: {error}"
        )


# ==========================================================
# MAIN