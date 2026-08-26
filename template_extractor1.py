import os
import re
import sys
import json
from collections import OrderedDict


# ==========================================================
# START
#
# Primer:
# python3 template_extractor.py /path/to/log/folder
# ==========================================================

if len(sys.argv) < 2:
    print("Usage: python3 template_extractor.py FOLDER")
    sys.exit(1)


ROOT = os.path.abspath(sys.argv[1])


# ==========================================================
# OUTPUT
# ==========================================================

OUTPUT_SUMMARY = os.path.join(
    ROOT,
    "template_summary.json"
)

OUTPUT_EVENTS = os.path.join(
    ROOT,
    "event_sequence.jsonl"
)


# ==========================================================
# BINARNYE FORMATY KOTORYE PROPUSKAEM
# ==========================================================

SKIP_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".sys",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".mp3",
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".zip",
    ".rar",
    ".7z",
    ".gz",
    ".tar",
    ".iso",
    ".bin",
    ".pdf",
}


# ==========================================================
# FAIL PATTERNS KOTORYE PROPUSKAEM
#
# Primer:
# file.log.1
# file.log.17
# file.log.999
# ==========================================================

SKIP_FILE_PATTERNS = [
    r"\.log\.\d+$",
]


# ==========================================================
# REGEX DYNAMIC VALUES
# ==========================================================

TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}"
    r"[ T]"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?\b"
)


DATE_TIME_RE = re.compile(
    r"\b\d{2}/\d{2}/\d{4}"
    r"\s+"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?\b"
)


# Primer:
# 04.02.2026,346
# 04.02.2026,575
# 05.03.2026,773
DATE_EVENT_RE = re.compile(
    r"\b\d{2}\.\d{2}\.\d{4},\d+\b"
)


UUID_RE = re.compile(
    r"\b"
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
    r"\b"
)


IPV4_RE = re.compile(
    r"\b"
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"\b"
)


MAC_RE = re.compile(
    r"\b"
    r"(?:[0-9A-Fa-f]{2}:){5}"
    r"[0-9A-Fa-f]{2}"
    r"\b"
)


HEX_RE = re.compile(
    r"\b0x[0-9A-Fa-f]+\b"
)


NUMBER_RE = re.compile(
    r"(?<![\w.])"
    r"-?\d+(?:\.\d+)?"
    r"(?![\w.])"
)


# ==========================================================
# KEY : VALUE
#
# Primer:
# Firmware version: 5.2
# Status = ready
# Mode: legacy
# ==========================================================

KEY_VALUE_RE = re.compile(
    r"^(\s*[^:=]{1,100}?\s*[:=]\s*)"
    r"(.+?)"
    r"\s*$"
)


# ==========================================================
# PROVERKA FAILA
# ==========================================================

def should_skip_file(filename):

    extension = os.path.splitext(
        filename
    )[1].lower()

    if extension in SKIP_EXTENSIONS:
        return True

    for pattern in SKIP_FILE_PATTERNS:

        if re.search(
            pattern,
            filename,
            re.IGNORECASE
        ):
            return True

    return False


# ==========================================================
# POLUCHIT PERVUJU PAPKU POSLE ROOT
# ==========================================================

def get_top_directory(directory):

    relative = os.path.relpath(
        directory,
        ROOT
    )

    if relative == ".":
        return "ROOT"

    return relative.split(
        os.sep
    )[0]


# ==========================================================
# ZAMENA REGEX S SOHRANENIEM REALNYH VALUES
# ==========================================================

def replace_and_collect(
    text,
    regex,
    placeholder,
    value_type,
    values
):

    def replacement(match):

        values.append({
            "type": value_type,
            "value": match.group(0)
        })

        return placeholder

    return regex.sub(
        replacement,
        text
    )


# ==========================================================
# POSTROENIE TEMPLATE IZ STROKI
# ==========================================================

def make_template(line):

    original = line.rstrip(
        "\r\n"
    )

    text = original

    values = []


    # ------------------------------------------------------
    # Timestamp
    # ------------------------------------------------------

    text = replace_and_collect(
        text,
        TIMESTAMP_RE,
        "<TIMESTAMP>",
        "timestamp",
        values
    )


    text = replace_and_collect(
        text,
        DATE_TIME_RE,
        "<TIMESTAMP>",
        "timestamp",
        values
    )


    # ------------------------------------------------------
    # Date event
    #
    # Primer:
    # 04.02.2026,346
    #
    # ->
    #
    # <DATE_EVENT>
    # ------------------------------------------------------

    text = replace_and_collect(
        text,
        DATE_EVENT_RE,
        "<DATE_EVENT>",
        "date_event",
        values
    )


    # ------------------------------------------------------
    # UUID
    # ------------------------------------------------------

    text = replace_and_collect(
        text,
        UUID_RE,
        "<UUID>",
        "uuid",
        values
    )


    # ------------------------------------------------------
    # IP
    # ------------------------------------------------------

    text = replace_and_collect(
        text,
        IPV4_RE,
        "<IP>",
        "ipv4",
        values
    )


    # ------------------------------------------------------
    # MAC
    # ------------------------------------------------------

    text = replace_and_collect(
        text,
        MAC_RE,
        "<MAC>",
        "mac",
        values
    )


    # ------------------------------------------------------
    # HEX
    # ------------------------------------------------------

    text = replace_and_collect(
        text,
        HEX_RE,
        "<HEX>",
        "hex",
        values
    )


    # ------------------------------------------------------
    # KEY : VALUE
    # ------------------------------------------------------

    kv_match = KEY_VALUE_RE.match(
        text
    )

    if kv_match:

        left = kv_match.group(1)
        right = kv_match.group(2)

        if right.strip():

            values.append({
                "type": "key_value",
                "value": right.strip()
            })

            text = (
                left
                + "<VALUE>"
            )

            return (
                text,
                values
            )


    # ------------------------------------------------------
    # Obychnye chisla
    #
    # Primer:
    # SSH attempt 45 failed
    #
    # ->
    #
    # SSH attempt <NUM> failed
    # ------------------------------------------------------

    text = replace_and_collect(
        text,
        NUMBER_RE,
        "<NUM>",
        "number",
        values
    )


    return (
        text,
        values
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    if not os.path.isdir(ROOT):

        print(
            f"Directory not found: {ROOT}"
        )

        sys.exit(1)


    templates = OrderedDict()

    total_files = 0
    total_lines = 0
    total_events = 0


    # Ochishchaem staryj event_sequence.jsonl
    with open(
        OUTPUT_EVENTS,
        "w",
        encoding="utf-8"
    ):
        pass


    # ======================================================
    # REKURSIVNYJ OBHOD
    # ======================================================

    for directory, subdirectories, files in os.walk(
        ROOT
    ):

        top_directory = get_top_directory(
            directory
        )


        for filename in files:

            if filename in {
                "template_summary.json",
                "event_sequence.jsonl"
            }:
                continue


            if should_skip_file(
                filename
            ):
                continue


            file_path = os.path.join(
                directory,
                filename
            )


            relative_path = os.path.relpath(
                file_path,
                ROOT
            )


            print(
                f"Scanning: {relative_path}",
                flush=True
            )


            total_files += 1


            try:

                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                    errors="ignore"
                ) as file:


                    for line_number, line in enumerate(
                        file,
                        start=1
                    ):

                        total_lines += 1


                        if not line.strip():
                            continue


                        template, values = make_template(
                            line
                        )


                        if not template.strip():
                            continue


                        total_events += 1


                        # ==================================
                        # TEMPLATE SUMMARY
                        # ==================================

                        if template not in templates:

                            templates[template] = {
                                "template": template,
                                "count": 0,
                                "examples": [],
                                "values": []
                            }


                        item = templates[
                            template
                        ]

                        item["count"] += 1


                        # Sohranjaem tolko 5 primerov
                        if len(
                            item["examples"]
                        ) < 5:

                            item["examples"].append({
                                "file": relative_path,
                                "line": line_number,
                                "text": line.rstrip(
                                    "\r\n"
                                )
                            })


                        # Sohranjaem ogranichennoe kolichestvo values
                        if (
                            values
                            and len(
                                item["values"]
                            ) < 100
                        ):

                            item["values"].append({
                                "file": relative_path,
                                "line": line_number,
                                "values": values
                            })


                        # ==================================
                        # EVENT SEQUENCE
                        # ==================================

                        event = {
                            "directory": top_directory,
                            "file": relative_path,
                            "line": line_number,
                            "template": template,
                            "values": values
                        }


                        with open(
                            OUTPUT_EVENTS,
                            "a",
                            encoding="utf-8"
                        ) as output:

                            output.write(
                                json.dumps(
                                    event,
                                    ensure_ascii=False
                                )
                                + "\n"
                            )


            except (
                PermissionError,
                OSError
            ):

                print(
                    f"Cannot read: {file_path}"
                )

                continue


    # ======================================================
    # SUMMARY JSON
    # ======================================================

    summary = {
        "root": ROOT,

        "statistics": {
            "files": total_files,
            "lines": total_lines,
            "events": total_events,
            "unique_templates": len(
                templates
            )
        },

        "templates": list(
            templates.values()
        )
    }


    with open(
        OUTPUT_SUMMARY,
        "w",
        encoding="utf-8"
    ) as output:

        json.dump(
            summary,
            output,
            indent=2,
            ensure_ascii=False
        )


    # ======================================================
    # RESULT
    # ======================================================

    print()
    print(
        "=" * 70
    )

    print(
        "TEMPLATE EXTRACTION COMPLETED"
    )

    print(
        "=" * 70
    )

    print(
        f"Files:             {total_files}"
    )

    print(
        f"Lines:             {total_lines}"
    )

    print(
        f"Events:            {total_events}"
    )

    print(
        f"Unique templates:  {len(templates)}"
    )

    print()

    print(
        "Summary:"
    )

    print(
        OUTPUT_SUMMARY
    )

    print()

    print(
        "Event sequence:"
    )

    print(
        OUTPUT_EVENTS
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()