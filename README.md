# Replay-Fidelity Auditor

Replay-Fidelity Auditor is a lightweight structural audit tool for conversational AI datasets.

It checks whether dataset records preserve enough structure to support deterministic multi-turn replay, including:

- enumerable turns
- user/assistant role attribution
- minimum alternation depth
- missing required roles
- simple truncation / summary markers

This tool was created to support the paper:

**Replay-Fidelity: A Structural Audit of Public Conversational AI Datasets for Deterministic Replay**

The auditor is intentionally conservative and structural. It does not reconstruct conversations, evaluate model quality, perform adversarial testing, or modify datasets.

## Reproducibility

This script is preserved close to the version used for the paper audit so readers can reproduce the reported structural checks.

Some role mappings are dataset-specific and are documented rather than removed. For example, some public conversational datasets encode assistant-side turns under labels such as `bot`, `gpt`, `chatgpt`, `bard`, or `system`. For the purpose of reproducing the paper’s audit behavior, those labels may be normalized to `assistant`.

This does not mean that all system messages are semantically equivalent to assistant replies in every dataset. It means the auditor follows the structural mapping used during the reported audit.

## Scope and limitations

This tool was written for the dataset structures evaluated in the Replay-Fidelity paper.

It is not a universal conversational-dataset parser. Public dialogue datasets use many different schemas, role labels, nesting formats, metadata conventions, and turn-boundary structures. If this auditor is used on datasets outside the paper, the extraction and role-mapping logic may need to be modified before the results are meaningful.

In particular, users may need to adjust:

- turn container keys
- role field names
- content field names
- role normalization rules
- metadata-based role mapping
- dataset-specific truncation or summary markers

The auditor should therefore be treated as a reproducibility tool for the paper and a starting point for structural replay-fidelity checks, not as a finished general-purpose standard.

## Usage

Run the auditor on a JSON or JSONL dataset:

```bash
python3 replay_fidelity_audit.py dataset.json
```

or:

```bash
python3 replay_fidelity_audit.py dataset.jsonl
```

For datasets where role information is encoded through metadata shape, use:

```bash
python3 replay_fidelity_audit.py dataset.json --role-map metadata_empty=user,metadata_nonempty=assistant
```

## Output

The tool prints aggregate counts for:

- `REPLAY_OK`
- `REPLAY_PARTIAL`
- `REPLAY_INVALID`

It also reports failure-mode distributions for partial and invalid records.

Example output format:

```text
Replay-Fidelity Audit Results
========================================
ROLE_MAPPING_MODE: EXPLICIT_ROLE_ONLY

Total records: 100

REPLAY_OK      :    75 ( 75.00%)
REPLAY_PARTIAL :    20 ( 20.00%)
REPLAY_INVALID :     5 (  5.00%)

----------------------------------------
FAILURE MODE DISTRIBUTION
----------------------------------------

PARTIAL:
  INSUFFICIENT_ALTERNATION           :    12
  TRUNCATION_OR_SUMMARY_DETECTED     :     8

INVALID:
  MISSING_REQUIRED_ROLE              :     5

Audit complete. No reconstruction performed.
```

## Verdict meanings

`REPLAY_OK` means the record contains enumerable turns, recognizable user/assistant roles, sufficient alternation depth, and no detected truncation or summary markers.

`REPLAY_PARTIAL` means the record contains some replay-relevant structure, but not enough to support clean deterministic replay under the audit rules.

`REPLAY_INVALID` means the record is missing core replay structure, such as enumerable turns or required roles.

## Related paper

**Replay-Fidelity: A Structural Audit of Public Conversational AI Datasets for Deterministic Replay**

Paper repository:

https://github.com/MitchBaba/replay-fidelity-paper

## Author

Mitchell Ryan Baba  
Founder / Lead Researcher, DriftForge Systems

## Contact

contact@driftforge.systems
