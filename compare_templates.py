import json
import sys
import os
import re
from collections import defaultdict


# ==========================================================
# START
#
# Primer:
#
# python3 compare_templates.py \
#     PASS_RUN/template_summary.json \
#     FAIL/template_summary.json
# ==========================================================

if len(sys.argv) < 3:
    print(
        "Usage: python3 compare_templates.py "
        "PASS_SUMMARY.json FAIL_SUMMARY.json"
    )
    sys.exit(1)


PASS_FILE = os.path.abspath(sys.argv[1])
FAIL_FILE = os.path.abspath(sys.argv[2])


OUTPUT_DIR = os.path.dirname(FAIL_FILE)

OUTPUT_TXT = os.path.join(
    OUTPUT_DIR,
    "comparison_report.txt"
)

OUTPUT_JSON = os.path.join(
    OUTPUT_DIR,
    "comparison_report.json"
)


# ==========================================================
# SETTINGS
# ==========================================================

# Esli FAIL count v stolko raz bolshe PASS,
# pokazhem ego kak zametnoe razlichie.
COUNT_RATIO_THRESHOLD = 3.0

# Ne pokazhemsja iz-za raznicy 1 protiv 2.
COUNT_MIN_DIFFERENCE = 5

# Skolko values pokazyvat v otchete.
MAX_VALUES_TO_SHOW = 20


# ==========================================================
# LOAD JSON
# ==========================================================

def load_summary(path):

    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ==========================================================
# CANONICAL TEMPLATE
#
# Udaljaem tolko tipichnyj sluzhebnyj prefix.
#
# Primer:
#
# <TIMESTAMP> [INFO ][SITE_1 ][692608000023]
# <DATE_EVENT> - INFO - test
#
# stanet:
#
# <DATE_EVENT> - INFO - test
#
# VAZHNO:
# Samo soobshchenie posle prefix my ne menjaem.
# ==========================================================

def canonicalize_template(template):

    text = template.strip()

    original = text


    # Udalit odin ili neskolko <TIMESTAMP> v nachale
    text = re.sub(
        r"^(?:<TIMESTAMP>\s*)+",
        "",
        text
    )


    # Udalit sluzhebnye blokи:
    #
    # [INFO ]
    # [SITE_1 ]
    # [692608000023]
    # [<NUM>]
    #
    # No tolko esli oni idut v nachale posle timestamp.
    text = re.sub(
        r"^(?:\[[^\]]*\]\s*)+",
        "",
        text
    )


    text = text.strip()


    # Esli my sluchajno ubrali vse,
    # vozvrashchaem original.
    if not text:
        return original


    return text


# ==========================================================
# COLLECT VALUES
#
# template_summary.json imeet:
#
# "values": [
#     {
#         "values": [
#             {
#                 "type": "key_value",
#                 "value": "..."
#             }
#         ]
#     }
# ]
# ==========================================================

def collect_values(template_item):

    result = defaultdict(set)

    for value_record in template_item.get(
        "values",
        []
    ):

        for value in value_record.get(
            "values",
            []
        ):

            value_type = value.get(
                "type",
                "unknown"
            )

            value_text = str(
                value.get(
                    "value",
                    ""
                )
            )

            if value_text:

                result[value_type].add(
                    value_text
                )

    return result


# ==========================================================
# BUILD CANONICAL INDEX
# ==========================================================

def build_index(summary):

    index = {}


    for item in summary.get(
        "templates",
        []
    ):

        original_template = item.get(
            "template",
            ""
        )

        canonical = canonicalize_template(
            original_template
        )


        if canonical not in index:

            index[canonical] = {
                "count": 0,
                "original_templates": [],
                "values": defaultdict(set)
            }


        entry = index[canonical]

        entry["count"] += item.get(
            "count",
            0
        )


        entry["original_templates"].append({
            "template": original_template,
            "count": item.get(
                "count",
                0
            )
        })


        values = collect_values(
            item
        )


        for value_type, items in values.items():

            entry["values"][
                value_type
            ].update(
                items
            )


    return index


# ==========================================================
# COUNT DIFFERENCE
# ==========================================================

def count_difference(pass_count, fail_count):

    difference = fail_count - pass_count


    if pass_count == 0:

        ratio = None

    else:

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
        "significant": significant
    }


# ==========================================================
# COMPARE VALUES
#
# Ne govorit "eto oshibka".
#
# Tolko pokazyvaet:
#
# PASS values
# FAIL values
# ==========================================================

def compare_values(
    pass_values,
    fail_values
):

    differences = []


    all_types = sorted(
        set(pass_values.keys())
        |
        set(fail_values.keys())
    )


    for value_type in all_types:

        pass_set = pass_values.get(
            value_type,
            set()
        )

        fail_set = fail_values.get(
            value_type,
            set()
        )


        # Timestamp/date_event my ne schitaem
        # diagnosticheskim otlichiem.
        #
        # Oni uzhe opredeleny kak dinamicheskij shum.
        if value_type in {
            "timestamp",
            "date_event"
        }:
            continue


        only_pass = pass_set - fail_set

        only_fail = fail_set - pass_set


        if only_pass or only_fail:

            differences.append({
                "type": value_type,

                "pass_values": sorted(
                    list(pass_set)
                )[
                    :MAX_VALUES_TO_SHOW
                ],

                "fail_values": sorted(
                    list(fail_set)
                )[
                    :MAX_VALUES_TO_SHOW
                ],

                "only_pass": sorted(
                    list(only_pass)
                )[
                    :MAX_VALUES_TO_SHOW
                ],

                "only_fail": sorted(
                    list(only_fail)
                )[
                    :MAX_VALUES_TO_SHOW
                ]
            })


    return differences


# ==========================================================
# MAIN
# ==========================================================

def main():

    pass_summary = load_summary(
        PASS_FILE
    )

    fail_summary = load_summary(
        FAIL_FILE
    )


    pass_index = build_index(
        pass_summary
    )

    fail_index = build_index(
        fail_summary
    )


    pass_templates = set(
        pass_index.keys()
    )

    fail_templates = set(
        fail_index.keys()
    )


    common = sorted(
        pass_templates
        &
        fail_templates
    )

    only_pass = sorted(
        pass_templates
        -
        fail_templates
    )

    only_fail = sorted(
        fail_templates
        -
        pass_templates
    )


    count_changes = []

    value_changes = []


    # ======================================================
    # COMMON TEMPLATES
    # ======================================================

    for template in common:

        pass_data = pass_index[
            template
        ]

        fail_data = fail_index[
            template
        ]


        count_info = count_difference(
            pass_data["count"],
            fail_data["count"]
        )


        if count_info["significant"]:

            count_changes.append({
                "template": template,
                "pass_count": pass_data[
                    "count"
                ],
                "fail_count": fail_data[
                    "count"
                ],
                "difference": count_info[
                    "difference"
                ],
                "ratio": count_info[
                    "ratio"
                ]
            })


        values = compare_values(
            pass_data["values"],
            fail_data["values"]
        )


        if values:

            value_changes.append({
                "template": template,
                "differences": values
            })


    # ======================================================
    # SORT
    # ======================================================

    count_changes.sort(
        key=lambda x: abs(
            x["difference"]
        ),
        reverse=True
    )


    # ======================================================
    # JSON RESULT
    # ======================================================

    report = {

        "pass_file": PASS_FILE,
        "fail_file": FAIL_FILE,

        "pass_statistics": pass_summary.get(
            "statistics",
            {}
        ),

        "fail_statistics": fail_summary.get(
            "statistics",
            {}
        ),

        "canonical_statistics": {
            "pass_templates": len(
                pass_templates
            ),
            "fail_templates": len(
                fail_templates
            ),
            "common": len(
                common
            ),
            "only_pass": len(
                only_pass
            ),
            "only_fail": len(
                only_fail
            )
        },

        "only_in_pass": only_pass,

        "only_in_fail": only_fail,

        "large_count_changes": count_changes,

        "value_changes": value_changes
    }


    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as output:

        json.dump(
            report,
            output,
            indent=2,
            ensure_ascii=False
        )


    # ======================================================
    # TXT REPORT
    # ======================================================

    with open(
        OUTPUT_TXT,
        "w",
        encoding="utf-8"
    ) as output:


        output.write(
            "=" * 80 + "\n"
        )

        output.write(
            "PASS vs FAIL TEMPLATE COMPARISON\n"
        )

        output.write(
            "=" * 80 + "\n\n"
        )


        output.write(
            f"PASS: {PASS_FILE}\n"
        )

        output.write(
            f"FAIL: {FAIL_FILE}\n\n"
        )


        # ----------------------------------------------
        # Statistics
        # ----------------------------------------------

        output.write(
            "SUMMARY\n"
        )

        output.write(
            "-" * 80 + "\n"
        )


        output.write(
            f"PASS raw templates: "
            f"{pass_summary.get('statistics', {}).get('unique_templates', 0)}\n"
        )

        output.write(
            f"FAIL raw templates: "
            f"{fail_summary.get('statistics', {}).get('unique_templates', 0)}\n"
        )

        output.write(
            f"PASS canonical templates: "
            f"{len(pass_templates)}\n"
        )

        output.write(
            f"FAIL canonical templates: "
            f"{len(fail_templates)}\n"
        )

        output.write(
            f"Common templates: "
            f"{len(common)}\n"
        )

        output.write(
            f"Only PASS: "
            f"{len(only_pass)}\n"
        )

        output.write(
            f"Only FAIL: "
            f"{len(only_fail)}\n"
        )


        # ----------------------------------------------
        # Count differences
        # ----------------------------------------------

        output.write(
            "\n\n"
            "=" * 80
            + "\n"
        )

        output.write(
            "LARGE COUNT DIFFERENCES\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        if not count_changes:

            output.write(
                "None\n"
            )


        for item in count_changes:

            output.write(
                f"TEMPLATE:\n"
                f"{item['template']}\n\n"
            )

            output.write(
                f"PASS count: {item['pass_count']}\n"
            )

            output.write(
                f"FAIL count: {item['fail_count']}\n"
            )

            output.write(
                f"Difference: {item['difference']:+d}\n"
            )


            if item["ratio"] is not None:

                output.write(
                    f"FAIL/PASS ratio: "
                    f"{item['ratio']:.2f}x\n"
                )


            output.write(
                "\n"
                + "-" * 80
                + "\n\n"
            )


        # ----------------------------------------------
        # Values
        # ----------------------------------------------

        output.write(
            "\n"
            "=" * 80
            + "\n"
        )

        output.write(
            "VALUE DIFFERENCES\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        if not value_changes:

            output.write(
                "None\n"
            )


        for item in value_changes:

            output.write(
                f"TEMPLATE:\n"
                f"{item['template']}\n\n"
            )


            for difference in item[
                "differences"
            ]:

                output.write(
                    f"Value type: "
                    f"{difference['type']}\n"
                )

                output.write(
                    "PASS values:\n"
                )

                for value in difference[
                    "pass_values"
                ]:

                    output.write(
                        f"  {value}\n"
                    )


                output.write(
                    "FAIL values:\n"
                )

                for value in difference[
                    "fail_values"
                ]:

                    output.write(
                        f"  {value}\n"
                    )


                output.write("\n")


            output.write(
                "-" * 80
                + "\n\n"
            )


        # ----------------------------------------------
        # Only FAIL
        # ----------------------------------------------

        output.write(
            "\n"
            "=" * 80
            + "\n"
        )

        output.write(
            "ONLY IN FAIL\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        for template in only_fail:

            output.write(
                f"{template}\n"
            )


        # ----------------------------------------------
        # Only PASS
        # ----------------------------------------------

        output.write(
            "\n\n"
            "=" * 80
            + "\n"
        )

        output.write(
            "ONLY IN PASS\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        for template in only_pass:

            output.write(
                f"{template}\n"
            )


    # ======================================================
    # SCREEN
    # ======================================================

    print()
    print("=" * 70)
    print("COMPARISON COMPLETED")
    print("=" * 70)

    print(
        f"PASS canonical templates: "
        f"{len(pass_templates)}"
    )

    print(
        f"FAIL canonical templates: "
        f"{len(fail_templates)}"
    )

    print(
        f"Common:                   "
        f"{len(common)}"
    )

    print(
        f"Only PASS:                "
        f"{len(only_pass)}"
    )

    print(
        f"Only FAIL:                "
        f"{len(only_fail)}"
    )

    print(
        f"Large count changes:      "
        f"{len(count_changes)}"
    )

    print(
        f"Value changes:            "
        f"{len(value_changes)}"
    )

    print()
    print(
        f"TXT report:  {OUTPUT_TXT}"
    )

    print(
        f"JSON report: {OUTPUT_JSON}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()