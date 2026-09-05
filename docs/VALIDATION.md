# Release candidate validation

Candidate: `0.2.0-rc.1`. Updated 2026-09-06. The results below distinguish code/package checks, instruction review, and actual host behavior.

| Check | Evidence | Limits |
|---|---|---|
| Offline model and packaging tests | 35 tests PASS on local macOS, Python 3.12.14 | Synthetic inputs; no native task execution |
| Official manifest and skill validators | PASS | Structure validation, not host integration or approval |
| Cross-platform CI | Six successful jobs: macOS, Windows, Ubuntu, each Python 3.10 and 3.14 | Revision-bound offline/package checks; [platform evidence](PLATFORM_SUPPORT.md) |
| Deterministic packages | Explicit file allowlist, sensitive text scan, normalized archive contents, SHA-256 output | Does not certify arbitrary future files or host behavior |
| Multilingual docs | English, Korean, Japanese, Simplified Chinese, Russian; local links checked | Main README translations; technical references are English |
| Independent instruction review | Stop/expiry, user decisions, partial history, missing acknowledgment reviewed | Text review, not executed host E2E |
| Bounded native-tool pilot | One instruction accepted by a native task-message tool | No correlated worker acknowledgment; orchestration effect not proven; closure check was late |
| Installed-plugin routing | NOT VERIFIED | A manual pilot is not an installation or fresh-chat test |
| Host-enforced OFF and unattended supervision | NOT VERIFIED / NOT PROVIDED | No lifecycle cancellation or background scheduler is shipped |

The pilot failed its timing acceptance check and did not establish causal orchestration success. Private customer data is excluded from this record and all release archives. No claim is made that all user project files or concurrent activity were independently audited.

The instruction review and pilot led to explicit decision-ID acknowledgment, separation of receipt/acceptance/completion, a hold on follow-on dispatch while an acknowledgment is unknown, clock checks before observations and sends, no unrelated long work during timed pilots, and no closure messages after expiry or user stop. Read-only observation has a zero-dispatch budget. These are instruction-level corrections; host-enforced timer/revocation guarantees and a successful installed-plugin retest remain outstanding.

## Reproduce the local checks

Use Python 3.10 or newer. Install `requirements-dev.txt` in an isolated environment for validators and portable IANA timezone data, then run:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate_package.py
python3 scripts/build_release.py
```

Generated archives and their checksums are written to `dist/`. Review the exact final archive and source revision; a prior CI run does not validate later instruction edits. The GitHub workflow runs the same synthetic checks across the six platform/interpreter combinations and has no publication step.

## Public approval gates still open

- Execute installed-plugin invocation and a disposable native Act test with correlated acknowledgment and completion evidence.
- Verify bounded observation, user stop, and zero further dispatch after stop/expiry on the actual host.
- Decide whether the narrower finite workflow is an acceptable release despite the original complete-OFF and unattended goals remaining unmet.
- Confirm final public product/privacy/terms/support URLs and complete the publisher's accurate portal review.
- Obtain the user's decision before review submission or public publication.
