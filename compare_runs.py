import os
import sys
import re
import json
from collections import defaultdict
from difflib import SequenceMatcher


# ==========================================================
# START
#
# Primer Windows:
#
# python compare_runs.py PASS_RUN FAIL
#
# Primer:
#
# python .\compare_runs.py ".\PASS_RUN" ".\FAIL"
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

# Vo skolko raz count dolzhen otlichatsja,
# chtoby my pokazali ego kak frequency anomaly.
COUNT_RATIO_THRESHOLD = 3.0


# Minimalnaja absoljutnaja raznica count.
COUNT_MIN_DIFFERENCE = 5


# Skolko realnyh values hranit na odin template.
MAX_VALUES = 50


# Skolko structural differences pokazat na odin fail.
MAX_STRUCTURAL_DIFFERENCES = 100


# Skolko sobytij pokazat v structural block.
MAX_SEQUENCE_CONTEXT = 8


# ==========================================================
# DYNAMIC VALUES KOTORYE NE SRAVNIVAEM
#
# Oni uzhe rassmatrivajutsja kak shum.
# ==========================================================

IGNORED_VALUE_TYPES = {
    "timestamp",
    "date_event",
}


# ==========================================================
# REDACTION
#
# Ne zapisivat paroli v report.
# ==========================================================

PASSWORD_RE = re.compile(
    r"(?i)(--password\s+)(\S+)"
)


def redact(text):

    if text is None:
        return text

    text = str(text)

    return PASSWORD_RE.sub(
        r"\1<REDACTED>",
        text
    )


# ==========================================================
# CANONICAL TEMPLATE
#
# Udaljaem sluzhebnyj prefix:
#
# <TIMESTAMP> [INFO ][SITE_1 ][692608000023]
#
# no ostavljaem samo soobshchenie.
# ==========================================================

def canonicalize_template(template):

    text = template.strip()

    original = text


    # Udaljaem timestamp v samom nachale.
    text = re.sub(
        r"^(?:<TIMESTAMP>\s*)+",
        "",
        text
    )


    # Udaljaem sluzhebnye [] bloki v nachale.
    #
    # Primer:
    #
    # [INFO ]
    # [SITE_1 ]
    # [692608000023]
    # [<NUM>]
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
# HELPER: ADD VALUE
# ==========================================================

def add_value(
    storage,
    value_type,
    value
):

    if value_type in IGNORED_VALUE_TYPES:
        return

    value = redact(
        value
    )

    if len(
        storage[value_type]
    ) >= MAX_VALUES:
        return

    storage[value_type].add(
        value
    )


# ==========================================================
# FILE MODEL
#
# Dlja kazhdogo faila hranim:
#
# counts:
#   skolko raz vstretilsja template
#
# values:
#   realnye dinamicheskie values
#
# sequence:
#   posledovatelnost template,
#   no povtory podriad szhimajutsja.
#
# Primer:
#
# A
# A
# A
# A
# B
#
# ->
#
# A count=4
# B count=1
# ==========================================================

def new_file_model():

    return {
        "counts": defaultdict(int),

        "values": defaultdict(
            lambda: defaultdict(set)
        ),

        "sequence": [],

        "line_start": None,
        "line_end": None,

        "event_count": 0,
    }


# ==========================================================
# ADD EVENT TO FILE MODEL
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


    if model["line_start"] is None:
        model["line_start"] = line_number

    model["line_end"] = line_number

    model["event_count"] += 1


    # ------------------------------------------
    # COUNT
    # ------------------------------------------

    model["counts"][
        template
    ] += 1


    # ------------------------------------------
    # VALUES
    # ------------------------------------------

    for value_item in event.get(
        "values",
        []
    ):

        value_type = value_item.get(
            "type",
            "unknown"
        )

        value = value_item.get(
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


    # ------------------------------------------
    # RUN LENGTH SEQUENCE
    #
    # Povtory odinakovogo template podriad
    # hranim odnim blokom.
    # ------------------------------------------

    if (
        model["sequence"]
        and model["sequence"][-1]["template"]
        == template
    ):

        model["sequence"][-1][
            "count"
        ] += 1

        model["sequence"][-1][
            "last_line"
        ] = line_number

    else:

        model["sequence"].append({
            "template": template,
            "count": 1,
            "first_line": line_number,
            "last_line": line_number,
        })


# ==========================================================
# LOAD EVENT_SEQUENCE.JSONL
#
# Chitaem postrochno.
#
# Vozvrashchaem:
#
# tests[test_name][relative_file] = model
# ==========================================================

def load_run(event_file):

    if not os.path.isfile(
        event_file
    ):

        print(
            f"Event file not found: {event_file}"
        )

        sys.exit(1)


    tests = defaultdict(dict)

    bad_lines = 0
    total_events = 0


    print(
        f"Reading: {event_file}",
        flush=True
    )


    with open(
        event_file,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:


        for json_line_number, raw in enumerate(
            file,
            start=1
        ):

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


            relative_file = event.get(
                "file",
                "UNKNOWN"
            )


            if relative_file not in tests[
                test_name
            ]:

                tests[
                    test_name
                ][
                    relative_file
                ] = new_file_model()


            add_event_to_model(
                tests[test_name][
                    relative_file
                ],
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


    print(
        f"Completed: {total_events:,} events"
    )


    if bad_lines:

        print(
            f"Warning: {bad_lines} "
            f"invalid JSONL lines skipped"
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


    if pass_count == 0:

        ratio = None

    else:

        ratio = (
            fail_count
            /
            pass_count
        )


    significant = False


    if (
        abs(difference)
        >= COUNT_MIN_DIFFERENCE
    ):

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

            "pass_values": sorted(
                list(pass_set)
            ),

            "fail_values": sorted(
                list(fail_set)
            ),
        })


    return result


# ==========================================================
# STRUCTURAL SEQUENCE COMPARISON
#
# SequenceMatcher sravnivaet uzhe szhatuju
# posledovatelnost logical templates.
#
# Eto ne prostoe line-by-line sravnenie.
# ==========================================================

def compare_sequences(
    pass_sequence,
    fail_sequence
):

    pass_templates = [
        item["template"]
        for item in pass_sequence
    ]

    fail_templates = [
        item["template"]
        for item in fail_sequence
    ]


    matcher = SequenceMatcher(
        None,
        pass_templates,
        fail_templates,
        autojunk=False
    )


    differences = []


    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue


        pass_block = (
            pass_sequence[
                i1:i2
            ]
        )

        fail_block = (
            fail_sequence[
                j1:j2
            ]
        )


        difference = {
            "type": tag.upper(),

            "pass_block": pass_block[
                :MAX_SEQUENCE_CONTEXT
            ],

            "fail_block": fail_block[
                :MAX_SEQUENCE_CONTEXT
            ],
        }


        differences.append(
            difference
        )


        if (
            len(differences)
            >= MAX_STRUCTURAL_DIFFERENCES
        ):
            break


    return differences


# ==========================================================
# COMPARE ONE FILE
# ==========================================================

def compare_file(
    test_name,
    file_name,
    pass_model,
    fail_model
):

    result = {

        "test": test_name,
        "file": file_name,

        "pass_events": pass_model[
            "event_count"
        ],

        "fail_events": fail_model[
            "event_count"
        ],

        "count_differences": [],

        "value_differences": [],

        "structural_differences": [],
    }


    # ======================================================
    # TEMPLATE COUNTS
    # ======================================================

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

                "pass_count": pass_count,

                "fail_count": fail_count,

                "difference": count_info[
                    "difference"
                ],

                "ratio": count_info[
                    "ratio"
                ],
            })


        # ==============================================
        # VALUES
        # ==============================================

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


        value_differences = (
            compare_template_values(
                pass_values,
                fail_values
            )
        )


        if value_differences:

            result[
                "value_differences"
            ].append({

                "template": template,

                "differences":
                    value_differences,
            })


    # ======================================================
    # STRUCTURAL SEQUENCE
    # ======================================================

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
#
# defaultdict/set ne mogut byt zapisany
# v JSON naprjamu.
# ==========================================================

def serializable(obj):

    if isinstance(
        obj,
        defaultdict
    ):

        obj = dict(
            obj
        )


    if isinstance(
        obj,
        dict
    ):

        return {
            key: serializable(value)
            for key, value in obj.items()
        }


    if isinstance(
        obj,
        list
    ):

        return [
            serializable(value)
            for value in obj
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

    # ======================================================
    # LOAD PASS + FAIL
    # ======================================================

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


    # ======================================================
    # TEST STRUCTURE
    # ======================================================

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

        "common_tests": common_tests,

        # VAZHNO:
        # My poka ne govorim tochno,
        # chto oni NOT EXECUTED.
        #
        # Tolko: ih net v FAIL.
        "tests_only_in_pass":
            only_pass_tests,

        "tests_only_in_fail":
            only_fail_tests,

        "files_only_in_pass": [],

        "files_only_in_fail": [],

        "file_comparisons": [],
    }


    # ======================================================
    # COMPARE COMMON TESTS
    # ======================================================

    for test_name in common_tests:

        print(
            f"Comparing test: "
            f"{test_name}",
            flush=True
        )


        pass_files = set(
            pass_tests[
                test_name
            ].keys()
        )

        fail_files = set(
            fail_tests[
                test_name
            ].keys()
        )


        common_files = sorted(
            pass_files
            &
            fail_files
        )


        only_pass_files = sorted(
            pass_files
            -
            fail_files
        )


        only_fail_files = sorted(
            fail_files
            -
            pass_files
        )


        for file_name in only_pass_files:

            report[
                "files_only_in_pass"
            ].append({

                "test": test_name,

                "file": file_name,
            })


        for file_name in only_fail_files:

            report[
                "files_only_in_fail"
            ].append({

                "test": test_name,

                "file": file_name,
            })


        # ==============================================
        # SAME RELATIVE FILE
        # ==============================================

        for file_name in common_files:

            comparison = compare_file(

                test_name,

                file_name,

                pass_tests[
                    test_name
                ][
                    file_name
                ],

                fail_tests[
                    test_name
                ][
                    file_name
                ]
            )


            # Sohranjaem tolko faily,
            # gde est hotja by odno otlichie.

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


    # ======================================================
    # FIND EARLIEST DIFFERENCE
    #
    # Na pervoj versii berem pervyj test/file,
    # gde nashlos otlichie.
    #
    # Poka eto ne root cause.
    # ======================================================

    earliest_difference = None


    if report[
        "file_comparisons"
    ]:

        first = report[
            "file_comparisons"
        ][0]


        earliest_difference = {

            "test": first[
                "test"
            ],

            "file": first[
                "file"
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
    ] = earliest_difference


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
    # TEXT REPORT
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


        # ==============================================
        # TEST STRUCTURE
        # ==============================================

        output.write(
            "=" * 80
            + "\n"
        )

        output.write(
            "TEST STRUCTURE\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        output.write(
            "Common tests:\n"
        )

        for test in common_tests:

            output.write(
                f"  {test}\n"
            )


        output.write(
            "\nPresent in PASS but not FAIL:\n"
        )

        for test in only_pass_tests:

            output.write(
                f"  {test}\n"
            )


        output.write(
            "\nPresent only in FAIL:\n"
        )

        for test in only_fail_tests:

            output.write(
                f"  {test}\n"
            )


        # ==============================================
        # EARLIEST DIFFERENCE
        # ==============================================

        output.write(
            "\n\n"
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


        if earliest_difference:

            output.write(
                f"Test: "
                f"{earliest_difference['test']}\n"
            )

            output.write(
                f"File: "
                f"{earliest_difference['file']}\n"
            )

            output.write(
                "NOTE: This is NOT automatically "
                "the root cause.\n"
            )

        else:

            output.write(
                "No difference detected "
                "in common files.\n"
            )


        # ==============================================
        # FILE DIFFERENCES
        # ==============================================

        for comparison in report[
            "file_comparisons"
        ]:


            output.write(
                "\n\n"
                "=" * 80
                + "\n"
            )

            output.write(
                f"TEST: {comparison['test']}\n"
            )

            output.write(
                f"FILE: {comparison['file']}\n"
            )

            output.write(
                "=" * 80
                + "\n"
            )


            output.write(
                f"\nPASS events: "
                f"{comparison['pass_events']}\n"
            )

            output.write(
                f"FAIL events: "
                f"{comparison['fail_events']}\n"
            )


            # ------------------------------------------
            # VALUE
            # ------------------------------------------

            if comparison[
                "value_differences"
            ]:

                output.write(
                    "\n"
                    "-" * 80
                    + "\n"
                )

                output.write(
                    "VALUE DIFFERENCES\n"
                )

                output.write(
                    "-" * 80
                    + "\n"
                )


                for item in comparison[
                    "value_differences"
                ]:

                    output.write(
                        f"\nTemplate:\n"
                        f"{item['template']}\n"
                    )


                    for difference in item[
                        "differences"
                    ]:

                        output.write(
                            f"\nValue type: "
                            f"{difference['value_type']}\n"
                        )


                        if difference[
                            "only_pass"
                        ]:

                            output.write(
                                "Only PASS:\n"
                            )

                            for value in difference[
                                "only_pass"
                            ]:

                                output.write(
                                    f"  {value}\n"
                                )


                        if difference[
                            "only_fail"
                        ]:

                            output.write(
                                "Only FAIL:\n"
                            )

                            for value in difference[
                                "only_fail"
                            ]:

                                output.write(
                                    f"  {value}\n"
                                )


            # ------------------------------------------
            # COUNT
            # ------------------------------------------

            if comparison[
                "count_differences"
            ]:

                output.write(
                    "\n"
                    "-" * 80
                    + "\n"
                )

                output.write(
                    "FREQUENCY / RETRY DIFFERENCES\n"
                )

                output.write(
                    "-" * 80
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


            # ------------------------------------------
            # STRUCTURAL
            # ------------------------------------------

            if comparison[
                "structural_differences"
            ]:

                output.write(
                    "\n"
                    "-" * 80
                    + "\n"
                )

                output.write(
                    "STRUCTURAL DIFFERENCES\n"
                )

                output.write(
                    "-" * 80
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
                        f"Type: {diff['type']}\n"
                    )


                    output.write(
                        "\nPASS block:\n"
                    )

                    for item in diff[
                        "pass_block"
                    ]:

                        output.write(
                            f"  "
                            f"[x{item['count']}] "
                            f"{item['template']}\n"
                        )


                    output.write(
                        "\nFAIL block:\n"
                    )

                    for item in diff[
                        "fail_block"
                    ]:

                        output.write(
                            f"  "
                            f"[x{item['count']}] "
                            f"{item['template']}\n"
                        )


        # ==============================================
        # FILES ONLY PASS / FAIL
        # ==============================================

        output.write(
            "\n\n"
            "=" * 80
            + "\n"
        )

        output.write(
            "FILES PRESENT ONLY IN PASS\n"
        )

        output.write(
            "=" * 80
            + "\n"
        )


        for item in report[
            "files_only_in_pass"
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
            "FILES PRESENT ONLY IN FAIL\n"
        )

        output.write(
            "=" * 80
            + "\n"
        )


        for item in report[
            "files_only_in_fail"
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
        f"Different files:    "
        f"{len(report['file_comparisons'])}"
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