import os
import sys
import re
import json
from collections import defaultdict
from difflib import SequenceMatcher


# ==========================================================
# START
# ==========================================================

if len(sys.argv) < 3:
    print(
        "Usage: python compare_runs.py "
        "PASS_FOLDER FAIL_FOLDER"
    )
    sys.exit(1)


PASS_ROOT = os.path.abspath(sys.argv[1])
FAIL_ROOT = os.path.abspath(sys.argv[2])

PASS_EVENTS_FILE = os.path.join(
    PASS_ROOT,
    "event_sequence.jsonl"
)

FAIL_EVENTS_FILE = os.path.join(
    FAIL_ROOT,
    "event_sequence.jsonl"
)

OUTPUT_TXT = os.path.join(
    FAIL_ROOT,
    "run_comparison_report.txt"
)

OUTPUT_JSON = os.path.join(
    FAIL_ROOT,
    "run_comparison_report.json"
)


# ==========================================================
# SETTINGS
# ==========================================================

COUNT_RATIO_THRESHOLD = 3.0
COUNT_MIN_DIFFERENCE = 5
MAX_VALUES = 50
MAX_STRUCTURAL_DIFFERENCES = 100
MAX_SEQUENCE_CONTEXT = 8


IGNORED_VALUE_TYPES = {
    "timestamp",
    "date_event",
}


# ==========================================================
# REDACTION
# ==========================================================

PASSWORD_RE = re.compile(
    r"(?i)(--password\s+)(\S+)"
)


def redact(text):

    if text is None:
        return text

    return PASSWORD_RE.sub(
        r"\1<REDACTED>",
        str(text)
    )


# ==========================================================
# NORMALIZE FILE NAME
#
# Primer:
#
# anora_power.py_2026-04-18-08_28_15.log
#
# ->
#
# anora_power.py_<DATETIME>.log
# ==========================================================

FILE_DATETIME_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}-\d{2}_\d{2}_\d{2}"
)


def normalize_filename(path):

    directory = os.path.dirname(path)

    filename = os.path.basename(path)

    normalized = FILE_DATETIME_RE.sub(
        "<DATETIME>",
        filename
    )

    if directory:

        return os.path.join(
            directory,
            normalized
        )

    return normalized


# ==========================================================
# CANONICAL TEMPLATE
# ==========================================================

def canonicalize_template(template):

    text = template.strip()
    original = text

    text = re.sub(
        r"^(?:<TIMESTAMP>\s*)+",
        "",
        text
    )

    text = re.sub(
        r"^(?:\[[^\]]*\]\s*)+",
        "",
        text
    )

    text = text.strip()

    if not text:
        return original

    return redact(text)


# ==========================================================
# FILE MODEL
# ==========================================================

def new_file_model():

    return {
        "counts": defaultdict(int),

        "values": defaultdict(
            lambda: defaultdict(set)
        ),

        "sequence": [],

        "event_count": 0,

        "first_line": None,
        "last_line": None,
    }


# ==========================================================
# ADD VALUE
# ==========================================================

def add_value(
    storage,
    value_type,
    value
):

    if value_type in IGNORED_VALUE_TYPES:
        return

    value = redact(value)

    if len(storage[value_type]) >= MAX_VALUES:
        return

    storage[value_type].add(
        value
    )


# ==========================================================
# ADD EVENT
# ==========================================================

def add_event_to_model(
    model,
    event
):

    template = canonicalize_template(
        event.get(
            "template",
            ""
        )
    )

    if not template:
        return


    line_number = event.get(
        "line"
    )


    if model["first_line"] is None:
        model["first_line"] = line_number

    model["last_line"] = line_number
    model["event_count"] += 1


    # Count
    model["counts"][template] += 1


    # Values
    for item in event.get(
        "values",
        []
    ):

        value_type = item.get(
            "type",
            "unknown"
        )

        value = item.get(
            "value",
            ""
        )

        if not value:
            continue

        add_value(
            model["values"][template],
            value_type,
            value
        )


    # Sequence compression
    if (
        model["sequence"]
        and model["sequence"][-1]["template"]
        == template
    ):

        model["sequence"][-1]["count"] += 1
        model["sequence"][-1]["last_line"] = line_number

    else:

        model["sequence"].append({
            "template": template,
            "count": 1,
            "first_line": line_number,
            "last_line": line_number,
        })


# ==========================================================
# LOAD RUN
#
# tests[test_name][normalized_file]
#     = [
#         {
#             "original_file": ...,
#             "model": ...
#         },
#         ...
#       ]
#
# Esli odin tip faila vstrechaetsja mnogo raz,
# hranim ego kak spisok.
# ==========================================================

def load_run(event_file):

    if not os.path.isfile(event_file):

        print(
            f"Event file not found: {event_file}"
        )

        sys.exit(1)


    tests = defaultdict(
        lambda: defaultdict(list)
    )

    total_events = 0
    bad_lines = 0


    print(
        f"Reading: {event_file}",
        flush=True
    )


    # Vremenno hranim model po original file
    original_models = {}


    with open(
        event_file,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        for raw in file:

            if not raw.strip():
                continue


            try:

                event = json.loads(
                    raw
                )

            except json.JSONDecodeError:

                bad_lines += 1
                continue


            total_events += 1


            test_name = event.get(
                "directory",
                "ROOT"
            )

            original_file = event.get(
                "file",
                "UNKNOWN"
            )


            key = (
                test_name,
                original_file
            )


            if key not in original_models:

                original_models[key] = new_file_model()


            add_event_to_model(
                original_models[key],
                event
            )


            if (
                total_events % 100000
                == 0
            ):

                print(
                    f"  Events read: "
                    f"{total_events:,}",
                    flush=True
                )


    # Posle chtenija gruppiruem po normalized filename
    for (
        test_name,
        original_file
    ), model in original_models.items():

        normalized_file = normalize_filename(
            original_file
        )

        tests[
            test_name
        ][
            normalized_file
        ].append({
            "original_file": original_file,
            "model": model
        })


    # Sort po imeni original faila.
    # U nas timestamp v imeni, poetomu porjadok
    # poluchitsja hronologicheskij.
    for test_name in tests:

        for normalized_file in tests[
            test_name
        ]:

            tests[
                test_name
            ][
                normalized_file
            ].sort(
                key=lambda x:
                x["original_file"]
            )


    print(
        f"Completed: {total_events:,} events"
    )


    if bad_lines:

        print(
            f"Warning: {bad_lines} invalid "
            f"JSONL lines skipped"
        )


    return tests


# ==========================================================
# COUNT DIFFERENCE
# ==========================================================

def get_count_difference(
    pass_count,
    fail_count
):

    difference = (
        fail_count
        -
        pass_count
    )


    ratio = None

    if pass_count > 0:
        ratio = fail_count / pass_count


    significant = False


    if abs(difference) >= COUNT_MIN_DIFFERENCE:

        if pass_count == 0:

            significant = True

        elif ratio >= COUNT_RATIO_THRESHOLD:

            significant = True

        elif ratio <= (
            1 / COUNT_RATIO_THRESHOLD
        ):

            significant = True


    return {
        "difference": difference,
        "ratio": ratio,
        "significant": significant,
    }


# ==========================================================
# COMPARE VALUES
# ==========================================================

def compare_template_values(
    pass_values,
    fail_values
):

    result = []


    all_types = (
        set(pass_values.keys())
        |
        set(fail_values.keys())
    )


    for value_type in sorted(
        all_types
    ):

        if value_type in IGNORED_VALUE_TYPES:
            continue


        pass_set = set(
            pass_values.get(
                value_type,
                set()
            )
        )

        fail_set = set(
            fail_values.get(
                value_type,
                set()
            )
        )


        only_pass = (
            pass_set
            -
            fail_set
        )

        only_fail = (
            fail_set
            -
            pass_set
        )


        if not (
            only_pass
            or only_fail
        ):
            continue


        result.append({
            "value_type": value_type,

            "only_pass": sorted(
                list(only_pass)
            ),

            "only_fail": sorted(
                list(only_fail)
            ),
        })


    return result


# ==========================================================
# SEQUENCE COMPARISON
# ==========================================================

def compare_sequences(
    pass_sequence,
    fail_sequence
):

    pass_templates = [
        x["template"]
        for x in pass_sequence
    ]

    fail_templates = [
        x["template"]
        for x in fail_sequence
    ]


    matcher = SequenceMatcher(
        None,
        pass_templates,
        fail_templates,
        autojunk=False
    )


    differences = []


    for (
        tag,
        i1,
        i2,
        j1,
        j2
    ) in matcher.get_opcodes():

        if tag == "equal":
            continue


        differences.append({

            "type": tag.upper(),

            "pass_block":
                pass_sequence[
                    i1:i2
                ][
                    :MAX_SEQUENCE_CONTEXT
                ],

            "fail_block":
                fail_sequence[
                    j1:j2
                ][
                    :MAX_SEQUENCE_CONTEXT
                ],
        })


        if (
            len(differences)
            >= MAX_STRUCTURAL_DIFFERENCES
        ):
            break


    return differences


# ==========================================================
# COMPARE ONE FILE PAIR
# ==========================================================

def compare_file_pair(
    test_name,
    normalized_file,
    pass_item,
    fail_item,
    pair_index
):

    pass_model = pass_item[
        "model"
    ]

    fail_model = fail_item[
        "model"
    ]


    result = {

        "test": test_name,

        "normalized_file":
            normalized_file,

        "pair_index":
            pair_index,

        "pass_file":
            pass_item[
                "original_file"
            ],

        "fail_file":
            fail_item[
                "original_file"
            ],

        "pass_events":
            pass_model[
                "event_count"
            ],

        "fail_events":
            fail_model[
                "event_count"
            ],

        "count_differences": [],

        "value_differences": [],

        "structural_differences": [],
    }


    all_templates = (
        set(
            pass_model[
                "counts"
            ].keys()
        )
        |
        set(
            fail_model[
                "counts"
            ].keys()
        )
    )


    for template in sorted(
        all_templates
    ):

        pass_count = pass_model[
            "counts"
        ].get(
            template,
            0
        )

        fail_count = fail_model[
            "counts"
        ].get(
            template,
            0
        )


        count_info = get_count_difference(
            pass_count,
            fail_count
        )


        if count_info[
            "significant"
        ]:

            result[
                "count_differences"
            ].append({

                "template": template,

                "pass_count":
                    pass_count,

                "fail_count":
                    fail_count,

                "difference":
                    count_info[
                        "difference"
                    ],

                "ratio":
                    count_info[
                        "ratio"
                    ],
            })


        pass_values = pass_model[
            "values"
        ].get(
            template,
            {}
        )

        fail_values = fail_model[
            "values"
        ].get(
            template,
            {}
        )


        differences = (
            compare_template_values(
                pass_values,
                fail_values
            )
        )


        if differences:

            result[
                "value_differences"
            ].append({

                "template":
                    template,

                "differences":
                    differences,
            })


    result[
        "structural_differences"
    ] = compare_sequences(

        pass_model[
            "sequence"
        ],

        fail_model[
            "sequence"
        ]
    )


    return result


# ==========================================================
# SERIALIZABLE
# ==========================================================

def serializable(obj):

    if isinstance(
        obj,
        defaultdict
    ):

        obj = dict(obj)


    if isinstance(
        obj,
        dict
    ):

        return {
            k: serializable(v)
            for k, v in obj.items()
        }


    if isinstance(
        obj,
        list
    ):

        return [
            serializable(x)
            for x in obj
        ]


    if isinstance(
        obj,
        set
    ):

        return sorted(
            list(obj)
        )


    return obj


# ==========================================================
# MAIN
# ==========================================================

def main():

    print()
    print("=" * 70)
    print("LOADING PASS")
    print("=" * 70)

    pass_tests = load_run(
        PASS_EVENTS_FILE
    )


    print()
    print("=" * 70)
    print("LOADING FAIL")
    print("=" * 70)

    fail_tests = load_run(
        FAIL_EVENTS_FILE
    )


    pass_test_names = set(
        pass_tests.keys()
    )

    fail_test_names = set(
        fail_tests.keys()
    )


    common_tests = sorted(
        pass_test_names
        &
        fail_test_names
    )


    only_pass_tests = sorted(
        pass_test_names
        -
        fail_test_names
    )


    only_fail_tests = sorted(
        fail_test_names
        -
        pass_test_names
    )


    report = {

        "pass_root": PASS_ROOT,
        "fail_root": FAIL_ROOT,

        "common_tests":
            common_tests,

        "tests_only_in_pass":
            only_pass_tests,

        "tests_only_in_fail":
            only_fail_tests,

        "unmatched_pass_files": [],

        "unmatched_fail_files": [],

        "file_comparisons": [],
    }


    # ======================================================
    # COMPARE TESTS
    # ======================================================

    for test_name in common_tests:

        print(
            f"Comparing test: {test_name}",
            flush=True
        )


        pass_groups = pass_tests[
            test_name
        ]

        fail_groups = fail_tests[
            test_name
        ]


        all_normalized_files = sorted(
            set(
                pass_groups.keys()
            )
            |
            set(
                fail_groups.keys()
            )
        )


        for normalized_file in all_normalized_files:

            pass_list = pass_groups.get(
                normalized_file,
                []
            )

            fail_list = fail_groups.get(
                normalized_file,
                []
            )


            # ------------------------------------------
            # Pair po porjadku
            # ------------------------------------------

            pair_count = min(
                len(pass_list),
                len(fail_list)
            )


            for index in range(
                pair_count
            ):

                comparison = compare_file_pair(

                    test_name,

                    normalized_file,

                    pass_list[index],

                    fail_list[index],

                    index + 1
                )


                if (
                    comparison[
                        "count_differences"
                    ]
                    or comparison[
                        "value_differences"
                    ]
                    or comparison[
                        "structural_differences"
                    ]
                ):

                    report[
                        "file_comparisons"
                    ].append(
                        comparison
                    )


            # ------------------------------------------
            # Unmatched PASS
            # ------------------------------------------

            if len(pass_list) > pair_count:

                for item in pass_list[
                    pair_count:
                ]:

                    report[
                        "unmatched_pass_files"
                    ].append({

                        "test":
                            test_name,

                        "normalized_file":
                            normalized_file,

                        "file":
                            item[
                                "original_file"
                            ],
                    })


            # ------------------------------------------
            # Unmatched FAIL
            # ------------------------------------------

            if len(fail_list) > pair_count:

                for item in fail_list[
                    pair_count:
                ]:

                    report[
                        "unmatched_fail_files"
                    ].append({

                        "test":
                            test_name,

                        "normalized_file":
                            normalized_file,

                        "file":
                            item[
                                "original_file"
                            ],
                    })


    # ======================================================
    # EARLIEST DIFFERENCE
    # ======================================================

    earliest = None


    if report[
        "file_comparisons"
    ]:

        first = report[
            "file_comparisons"
        ][0]


        earliest = {

            "test":
                first[
                    "test"
                ],

            "pass_file":
                first[
                    "pass_file"
                ],

            "fail_file":
                first[
                    "fail_file"
                ],

            "normalized_file":
                first[
                    "normalized_file"
                ],

            "pair_index":
                first[
                    "pair_index"
                ],

            "has_value_difference":
                bool(
                    first[
                        "value_differences"
                    ]
                ),

            "has_count_difference":
                bool(
                    first[
                        "count_differences"
                    ]
                ),

            "has_structural_difference":
                bool(
                    first[
                        "structural_differences"
                    ]
                ),
        }


    report[
        "earliest_detected_difference"
    ] = earliest


    # ======================================================
    # JSON
    # ======================================================

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as output:

        json.dump(
            serializable(
                report
            ),
            output,
            indent=2,
            ensure_ascii=False
        )


    # ======================================================
    # TXT
    # ======================================================

    with open(
        OUTPUT_TXT,
        "w",
        encoding="utf-8"
    ) as output:


        output.write(
            "=" * 80
            + "\n"
        )

        output.write(
            "PASS vs FAIL RUN ANALYSIS\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        output.write(
            f"PASS:\n{PASS_ROOT}\n\n"
        )

        output.write(
            f"FAIL:\n{FAIL_ROOT}\n\n"
        )


        # ------------------------------------------
        # EARLIEST
        # ------------------------------------------

        output.write(
            "=" * 80
            + "\n"
        )

        output.write(
            "EARLIEST DETECTED DIFFERENCE\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        if earliest:

            output.write(
                f"Test: {earliest['test']}\n"
            )

            output.write(
                f"Normalized file: "
                f"{earliest['normalized_file']}\n"
            )

            output.write(
                f"Pair: "
                f"{earliest['pair_index']}\n"
            )

            output.write(
                f"PASS file:\n"
                f"{earliest['pass_file']}\n"
            )

            output.write(
                f"FAIL file:\n"
                f"{earliest['fail_file']}\n"
            )

            output.write(
                "\nNOTE: This is NOT automatically "
                "the root cause.\n"
            )

        else:

            output.write(
                "No paired file difference "
                "detected.\n"
            )


        # ------------------------------------------
        # FILE COMPARISONS
        # ------------------------------------------

        for comparison in report[
            "file_comparisons"
        ]:


            output.write(
                "\n\n"
                "=" * 80
                + "\n"
            )

            output.write(
                f"TEST: "
                f"{comparison['test']}\n"
            )

            output.write(
                f"NORMALIZED FILE: "
                f"{comparison['normalized_file']}\n"
            )

            output.write(
                f"PAIR: "
                f"{comparison['pair_index']}\n"
            )

            output.write(
                f"PASS FILE:\n"
                f"{comparison['pass_file']}\n"
            )

            output.write(
                f"FAIL FILE:\n"
                f"{comparison['fail_file']}\n"
            )

            output.write(
                "=" * 80
                + "\n"
            )


            # VALUE
            if comparison[
                "value_differences"
            ]:

                output.write(
                    "\nVALUE DIFFERENCES\n"
                    + "-" * 80
                    + "\n"
                )


                for item in comparison[
                    "value_differences"
                ]:

                    output.write(
                        f"\nTemplate:\n"
                        f"{item['template']}\n"
                    )


                    for diff in item[
                        "differences"
                    ]:

                        output.write(
                            f"Value type: "
                            f"{diff['value_type']}\n"
                        )


                        if diff[
                            "only_pass"
                        ]:

                            output.write(
                                "Only PASS:\n"
                            )

                            for value in diff[
                                "only_pass"
                            ]:

                                output.write(
                                    f"  {value}\n"
                                )


                        if diff[
                            "only_fail"
                        ]:

                            output.write(
                                "Only FAIL:\n"
                            )

                            for value in diff[
                                "only_fail"
                            ]:

                                output.write(
                                    f"  {value}\n"
                                )


            # COUNT
            if comparison[
                "count_differences"
            ]:

                output.write(
                    "\nFREQUENCY / RETRY DIFFERENCES\n"
                    + "-" * 80
                    + "\n"
                )


                for item in comparison[
                    "count_differences"
                ]:

                    output.write(
                        f"\nTemplate:\n"
                        f"{item['template']}\n"
                    )

                    output.write(
                        f"PASS count: "
                        f"{item['pass_count']}\n"
                    )

                    output.write(
                        f"FAIL count: "
                        f"{item['fail_count']}\n"
                    )

                    output.write(
                        f"Difference: "
                        f"{item['difference']:+d}\n"
                    )


                    if item[
                        "ratio"
                    ] is not None:

                        output.write(
                            f"Ratio: "
                            f"{item['ratio']:.2f}x\n"
                        )


                    output.write(
                        "Classification: "
                        "BEHAVIORAL DIFFERENCE, "
                        "NOT CONFIRMED ROOT CAUSE\n"
                    )


            # STRUCTURAL
            if comparison[
                "structural_differences"
            ]:

                output.write(
                    "\nSTRUCTURAL DIFFERENCES\n"
                    + "-" * 80
                    + "\n"
                )


                for number, diff in enumerate(
                    comparison[
                        "structural_differences"
                    ],
                    start=1
                ):

                    output.write(
                        f"\nDifference #{number}\n"
                    )

                    output.write(
                        f"Type: "
                        f"{diff['type']}\n"
                    )


                    output.write(
                        "\nPASS block:\n"
                    )

                    for item in diff[
                        "pass_block"
                    ]:

                        output.write(
                            f"  [x{item['count']}] "
                            f"{item['template']}\n"
                        )


                    output.write(
                        "\nFAIL block:\n"
                    )

                    for item in diff[
                        "fail_block"
                    ]:

                        output.write(
                            f"  [x{item['count']}] "
                            f"{item['template']}\n"
                        )


        # ------------------------------------------
        # UNMATCHED
        # ------------------------------------------

        output.write(
            "\n\n"
            "=" * 80
            + "\n"
        )

        output.write(
            "UNMATCHED PASS FILES\n"
        )

        output.write(
            "=" * 80
            + "\n"
        )


        for item in report[
            "unmatched_pass_files"
        ]:

            output.write(
                f"{item['test']} -> "
                f"{item['file']}\n"
            )


        output.write(
            "\n\n"
            "=" * 80
            + "\n"
        )

        output.write(
            "UNMATCHED FAIL FILES\n"
        )

        output.write(
            "=" * 80
            + "\n"
        )


        for item in report[
            "unmatched_fail_files"
        ]:

            output.write(
                f"{item['test']} -> "
                f"{item['file']}\n"
            )


    # ======================================================
    # SCREEN
    # ======================================================

    print()
    print("=" * 70)
    print("RUN COMPARISON COMPLETED")
    print("=" * 70)

    print(
        f"Common tests:       "
        f"{len(common_tests)}"
    )

    print(
        f"PASS-only tests:    "
        f"{len(only_pass_tests)}"
    )

    print(
        f"FAIL-only tests:    "
        f"{len(only_fail_tests)}"
    )

    print(
        f"Different pairs:    "
        f"{len(report['file_comparisons'])}"
    )

    print(
        f"Unmatched PASS:     "
        f"{len(report['unmatched_pass_files'])}"
    )

    print(
        f"Unmatched FAIL:     "
        f"{len(report['unmatched_fail_files'])}"
    )

    print()

    print(
        f"TXT report:\n"
        f"{OUTPUT_TXT}"
    )

    print()

    print(
        f"JSON report:\n"
        f"{OUTPUT_JSON}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()