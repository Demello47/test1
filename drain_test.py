import os
import sys
import json
from collections import defaultdict

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig


# ==========================================================
# START
#
# Primer:
# python3 drain_test.py /path/to/log/folder
# ==========================================================

if len(sys.argv) < 2:
    print("Usage: python3 drain_test.py FOLDER")
    sys.exit(1)


ROOT = os.path.abspath(sys.argv[1])


OUTPUT_FILE = os.path.join(
    ROOT,
    "drain_templates.json"
)


# ==========================================================
# FORMATY KOTORYE NE SKANIRUEM
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
# DRAIN3 CONFIG
#
# Bez persistence:
# kazhdyj zapusk nachinaetsja s nulja.
# Dlja testa eto horosho.
# ==========================================================

config = TemplateMinerConfig()

config.profiling_enabled = False

# Glubina Drain tree
config.drain_depth = 4

# Minimalnoe similarity dlja obedinenija strok
# v odin template.
#
# 0.4 = dovolno gibko.
config.drain_sim_th = 0.4


template_miner = TemplateMiner(
    persistence_handler=None,
    config=config
)


# ==========================================================
# STATISTIKA PO FAILAM
# ==========================================================

file_templates = defaultdict(
    lambda: defaultdict(int)
)


total_files = 0
total_lines = 0


# ==========================================================
# PROVERKA FAILA
# ==========================================================

def should_skip(filename):

    extension = os.path.splitext(
        filename
    )[1].lower()

    if extension in SKIP_EXTENSIONS:
        return True

    if filename == "drain_templates.json":
        return True

    return False


# ==========================================================
# MAIN
# ==========================================================

def main():

    global total_files
    global total_lines


    if not os.path.isdir(ROOT):

        print(
            f"Directory not found: {ROOT}"
        )

        sys.exit(1)


    # ======================================================
    # OBUCHAEM DRAIN3 NA VSEH STROKAH
    # ======================================================

    for directory, subdirectories, files in os.walk(
        ROOT
    ):

        for filename in files:

            if should_skip(filename):
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


                    for line in file:

                        text = line.rstrip(
                            "\r\n"
                        )


                        if not text.strip():
                            continue


                        total_lines += 1


                        # ==================================
                        # DRAIN3
                        # ==================================

                        result = (
                            template_miner
                            .add_log_message(
                                text
                            )
                        )


                        cluster_id = result[
                            "cluster_id"
                        ]


                        file_templates[
                            relative_path
                        ][
                            cluster_id
                        ] += 1


                        if (
                            total_lines % 100000
                            == 0
                        ):

                            print(
                                f"Lines processed: "
                                f"{total_lines:,}",
                                flush=True
                            )


            except (
                PermissionError,
                OSError
            ) as error:

                print(
                    f"Cannot read: {file_path}"
                )


    # ======================================================
    # SOBIRAEM NAJDENNYE CLUSTERS
    # ======================================================

    clusters = []


    for cluster in template_miner.drain.clusters:

        template = cluster.get_template()

        clusters.append({

            "cluster_id":
                cluster.cluster_id,

            "count":
                cluster.size,

            "template":
                template
        })


    # Samye chastye sverhu
    clusters.sort(
        key=lambda x: x["count"],
        reverse=True
    )


    # ======================================================
    # FILE -> TEMPLATE COUNTS
    # ======================================================

    per_file = {}


    for file_name, cluster_counts in (
        file_templates.items()
    ):

        per_file[file_name] = []


        for cluster_id, count in (
            cluster_counts.items()
        ):

            cluster = (
                template_miner.drain
                .id_to_cluster[
                    cluster_id
                ]
            )


            per_file[
                file_name
            ].append({

                "cluster_id":
                    cluster_id,

                "count":
                    count,

                "template":
                    cluster.get_template()
            })


        per_file[
            file_name
        ].sort(
            key=lambda x: x["count"],
            reverse=True
        )


    # ======================================================
    # RESULT
    # ======================================================

    result = {

        "root":
            ROOT,

        "statistics": {

            "files":
                total_files,

            "lines":
                total_lines,

            "templates":
                len(clusters)
        },

        "templates":
            clusters,

        "files":
            per_file
    }


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as output:

        json.dump(
            result,
            output,
            indent=2,
            ensure_ascii=False
        )


    print()
    print("=" * 70)
    print("DRAIN3 TEST COMPLETED")
    print("=" * 70)

    print(
        f"Files:      "
        f"{total_files}"
    )

    print(
        f"Lines:      "
        f"{total_lines:,}"
    )

    print(
        f"Templates:  "
        f"{len(clusters):,}"
    )

    print()

    print(
        f"Output:"
    )

    print(
        OUTPUT_FILE
    )

    print("=" * 70)


if __name__ == "__main__":
    main()