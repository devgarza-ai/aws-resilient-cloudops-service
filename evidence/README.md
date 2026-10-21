# Public evidence

## Recovery observations

`recovery-observations.csv` is a normalized copy of the complete supplied probe record. All 265 rows remain in original order. Only identifying/calendar fields and verbose error text were transformed; status codes and request durations were preserved.

| Column | Meaning |
| --- | --- |
| `Sample` | Consecutive observation number beginning at 1 |
| `ElapsedSeconds` | Request-start offset from the first recorded request, preserving relative spacing |
| `HttpStatus` | Observed HTTP status; 0 is reserved for no HTTP response |
| `BackendRole` | `original`, `survivor`, or `replacement`; `unavailable` for the six error responses |
| `RequestDurationMs` | Original client-measured request duration |
| `ErrorCategory` | Empty on HTTP 200; `http-error` on the six HTTP 502 rows |

`recovery-summary.json` is calculated by [the analyzer](../scripts/analyze_recovery.py), including the public CSV's SHA-256 digest. The digest establishes which published bytes were analyzed; it is not a signature from AWS.

```bash
python3 scripts/analyze_recovery.py evidence/recovery-observations.csv --check evidence/recovery-summary.json
```

The [incident report](../docs/incidents/recovery-incident.md) explains the result and what the sample cannot establish.

## Audit extract

`audit-event.json` is a normalized extract of a successful CloudTrail management event found in a delivered log containing 42 events. It preserves the verified action, service, region, resource role, MFA flag, and success result. Original account/principal identifiers, source addresses, calendar fields, and the tag value are excluded.

## Config extract

`config-evaluations.json` summarizes inspected AWS Config resource rows: four compliant security groups and two compliant volumes. The project security groups are identified by logical name. Counts represent the selected rule views, not a comprehensive security audit of the account.

## Tool provenance

The bootstrap and agent settings correspond to the implemented service. The public PowerShell probe is a reusable adaptation and did not generate the committed historical observations. Private source records remain separate from the publication package.
