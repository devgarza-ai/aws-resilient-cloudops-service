# Evidence index

## Evidence standard

The public package separates measured observations, inspected configuration, owner-confirmed settings, and inferences. Original console captures and the original observer output were reviewed privately. Public artifacts preserve useful technical results without account IDs, credentials, source addresses, personal scheduling information, or calendar timestamps.

Normalized extracts are labeled as such. They are not presented as raw AWS service output or cryptographically verified transcripts.

| Claim | Public artifact | Verification boundary |
| --- | --- | --- |
| 265 sampled requests; 259 HTTP 200; six HTTP 502 | [Observation CSV](../evidence/recovery-observations.csv), [summary](../evidence/recovery-summary.json) | Sequential client sample; not continuous availability |
| Original, surviving, and replacement servers answered | `BackendRole` column in the CSV | Original hostnames replaced by consistent role aliases |
| Error-window span and successful tail | Recalculated by [analyze_recovery.py](../scripts/analyze_recovery.py) | Based on request-start measurements |
| Failed ELB health caused replacement | [Incident report](incidents/recovery-incident.md) | ASG Activity inspected in private console captures |
| Replacement and survivor ended healthy; alarm OK | [Incident report](incidents/recovery-incident.md) | Final target/ASG/alarm views inspected; exact OK transition absent |
| Replacement access and bootstrap events arrived | [Security and audit notes](security-and-audit.md) | Stream event presence inspected; error-event delivery not separately proven |
| A project tag change was audited | [Audit extract](../evidence/audit-event.json) | Delivered CloudTrail log parsed; successful event matched to the project instance |
| Security-group and volume rules returned Compliant | [Config extract](../evidence/config-evaluations.json) | Four security groups and two volumes in resource-level result views |
| Launch-template hardening settings | [Deployment notes](deployment.md) | Selected settings were owner-confirmed; the per-instance v2 label was cropped |
| Workload cost and budget alerts | [Cost status](costs.md) | Pending verification; no inferred success |

## Recovery data normalization

The full source CSV was parsed without dropping rows. Calendar timestamps were converted to elapsed seconds from the first request. Backend hostnames were consistently replaced with `original`, `survivor`, and `replacement`; the six failed HTTP responses have backend role `unavailable`. Error text was reduced to an error category. Response codes, request durations, row order, and relative request timing were preserved.

There are no reconstructed requests or synthetic successes in the published dataset. See [the data dictionary](../evidence/README.md) and [the incident](incidents/recovery-incident.md) for interpretation.

## Reproduce the numerical result

```bash
python3 scripts/analyze_recovery.py evidence/recovery-observations.csv --check evidence/recovery-summary.json
```

The analyzer validates sequential sample IDs, increasing elapsed starts, supported HTTP status values, durations, backend categories, and error consistency. It recalculates the summary and compares it with the committed file. Successful-request p95 uses the nearest-rank definition.

## Source and tooling boundaries

The deployment bootstrap and agent configuration correspond to the implemented setup. The public PowerShell observer is a reusable adaptation with an input URL, elapsed measurements, and a neutral output filename. It was reviewed but not executed against AWS as part of this release. Its future output must not be confused with the supplied normalized observations.

No AWS account mutation is performed by the local analysis, repository validation, or unit tests.
