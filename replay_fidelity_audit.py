#!/usr/bin/env python3
import json
import sys
from collections import Counter

MIN_ALTERNATING_TURNS = 4

TURN_CONTAINER_KEYS = (
    "turns",
    "messages",
    "log",
    "dialogue",
    "conversation",
    "conversations",
    "utterances",
)

CONTENT_KEYS = (
    "content",
    "text",
    "utterance",
    "message",
    "body",
)

ROLE_KEYS = (
    "role",
    "speaker",
    "author",
    "sender",
    "from",
)

ROLE_NORMALIZATION = {
    # User-side roles
    "user": "user",
    "human": "user",

    # Assistant-side roles
    "assistant": "assistant",
    "bot": "assistant",
    "system": "assistant",
    "gpt": "assistant",
    "chatgpt": "assistant",
    "bing": "assistant",
    "bard": "assistant",
}


# -----------------------------
# Loading
# -----------------------------

def load_records(path):
    records = []

    if path.endswith(".jsonl"):
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))

    elif path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.extend(data.values())
            else:
                raise RuntimeError("JSON must contain list or dict of records.")

    else:
        raise RuntimeError("Unsupported file type. Use .json or .jsonl")

    return records


# -----------------------------
# Extraction
# -----------------------------

def extract_turns(record):
    for key in TURN_CONTAINER_KEYS:
        if key in record and isinstance(record[key], list):
            return record[key]
    return None


def extract_role(turn):
    for key in ROLE_KEYS:
        if key in turn:
            raw_role = str(turn[key]).lower()
            return ROLE_NORMALIZATION.get(raw_role)
    return None


def extract_content(turn):
    for key in CONTENT_KEYS:
        if key in turn:
            return str(turn[key])
    return ""


# -----------------------------
# Metadata role mapping
# -----------------------------

def verify_metadata_role_invariant(records, empty_role, nonempty_role):
    for r_idx, record in enumerate(records):
        turns = extract_turns(record)
        if turns is None:
            raise RuntimeError("Cannot verify metadata invariant: turns not enumerable.")

        for t_idx, turn in enumerate(turns):
            if "metadata" not in turn:
                raise RuntimeError(
                    f"Invariant violation: Turn missing 'metadata' "
                    f"(record {r_idx}, turn {t_idx})"
                )

            if not isinstance(turn["metadata"], dict):
                raise RuntimeError(
                    f"Invariant violation: 'metadata' not dict "
                    f"(record {r_idx}, turn {t_idx})"
                )

    return True


def metadata_role_assign(turn, empty_role, nonempty_role):
    metadata = turn.get("metadata", None)
    if metadata is None:
        return None

    if not isinstance(metadata, dict):
        return None

    if metadata == {}:
        return empty_role
    else:
        return nonempty_role


# -----------------------------
# Structural analysis
# -----------------------------

def analyze_record(record, role_map=None):

    result = {
        "verdict": None,
        "reasons": [],
        "num_turns": 0,
        "num_user_turns": 0,
        "num_assistant_turns": 0,
        "alternation_depth": 0,
        "truncation_detected": False,
    }

    turns = extract_turns(record)

    if turns is None:
        result["verdict"] = "REPLAY_INVALID"
        result["reasons"].append("NO_ENUMERABLE_TURNS")
        return result

    if not isinstance(turns, list) or not turns:
        result["verdict"] = "REPLAY_INVALID"
        result["reasons"].append("EMPTY_TURN_LIST")
        return result

    last_role = None
    alternation_count = 0

    for turn in turns:
        if not isinstance(turn, dict):
            result["verdict"] = "REPLAY_INVALID"
            result["reasons"].append("NON_DICT_TURN")
            return result

        role = extract_role(turn)

        if role is None and role_map is not None:
            role = metadata_role_assign(
                turn,
                role_map["metadata_empty"],
                role_map["metadata_nonempty"],
            )

        content = extract_content(turn)
        result["num_turns"] += 1

        if role == "user":
            result["num_user_turns"] += 1
        elif role == "assistant":
            result["num_assistant_turns"] += 1
        else:
            continue

        if any(marker in content for marker in ["...", "…", "[truncated]", "[summary]"]):
            result["truncation_detected"] = True

        if last_role is None:
            alternation_count = 1
            last_role = role
        elif role != last_role:
            alternation_count += 1
            last_role = role

    result["alternation_depth"] = alternation_count

    if result["num_user_turns"] == 0 or result["num_assistant_turns"] == 0:
        result["verdict"] = "REPLAY_INVALID"
        result["reasons"].append("MISSING_REQUIRED_ROLE")
        return result

    if alternation_count < 2:
        result["verdict"] = "REPLAY_INVALID"
        result["reasons"].append("NO_MEANINGFUL_ALTERNATION")
        return result

    if alternation_count < MIN_ALTERNATING_TURNS:
        result["verdict"] = "REPLAY_PARTIAL"
        result["reasons"].append("INSUFFICIENT_ALTERNATION")
        return result

    if result["truncation_detected"]:
        result["verdict"] = "REPLAY_PARTIAL"
        result["reasons"].append("TRUNCATION_OR_SUMMARY_DETECTED")
        return result

    result["verdict"] = "REPLAY_OK"
    return result


# -----------------------------
# Main
# -----------------------------

def main():

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 replay_fidelity_audit.py <dataset.json>")
        print("  python3 replay_fidelity_audit.py <dataset.json> "
              "--role-map metadata_empty=user,metadata_nonempty=assistant")
        sys.exit(1)

    path = sys.argv[1]
    role_map = None

    if "--role-map" in sys.argv:
        idx = sys.argv.index("--role-map")
        mapping_str = sys.argv[idx + 1]

        parts = mapping_str.split(",")
        mapping = {}
        for p in parts:
            k, v = p.split("=")
            mapping[k.strip()] = v.strip()

        role_map = {
            "metadata_empty": mapping["metadata_empty"],
            "metadata_nonempty": mapping["metadata_nonempty"],
        }

    records = load_records(path)

    if role_map is not None:
        verify_metadata_role_invariant(
            records,
            role_map["metadata_empty"],
            role_map["metadata_nonempty"],
        )

    verdict_counts = Counter()
    failure_reason_counts = {
        "REPLAY_PARTIAL": Counter(),
        "REPLAY_INVALID": Counter(),
    }

    results = []

    for record in records:
        analysis = analyze_record(record, role_map=role_map)
        verdict = analysis["verdict"]

        verdict_counts[verdict] += 1
        results.append(analysis)

        if verdict in failure_reason_counts:
            for reason in analysis["reasons"]:
                failure_reason_counts[verdict][reason] += 1

    total = len(results)

    print("\nReplay-Fidelity Audit Results")
    print("=" * 40)

    if role_map is not None:
        print("ROLE_MAPPING_MODE: DECLARED")
        print(
            f"ROLE_MAPPING_RULE: "
            f"metadata_empty={role_map['metadata_empty']}, "
            f"metadata_nonempty={role_map['metadata_nonempty']}"
        )
        print("INVARIANT_VERIFICATION: PASSED\n")
    else:
        print("ROLE_MAPPING_MODE: EXPLICIT_ROLE_ONLY\n")

    print(f"Total records: {total}\n")

    for verdict in ("REPLAY_OK", "REPLAY_PARTIAL", "REPLAY_INVALID"):
        count = verdict_counts.get(verdict, 0)
        percent = (count / total * 100) if total else 0
        print(f"{verdict:15}: {count:5} ({percent:6.2f}%)")

    print("\n" + "-" * 40)
    print("FAILURE MODE DISTRIBUTION")
    print("-" * 40)

    for verdict in ("REPLAY_PARTIAL", "REPLAY_INVALID"):
        print(f"\n{verdict.replace('REPLAY_', '')}:")
        reasons = failure_reason_counts[verdict]
        if reasons:
            for reason in sorted(reasons):
                print(f"  {reason:35}: {reasons[reason]:5}")
        else:
            print("  (none)")

    print("\nAudit complete. No reconstruction performed.")


if __name__ == "__main__":
    main()
