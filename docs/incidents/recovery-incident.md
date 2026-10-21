# Recovery incident — application service failure

**Project:** Resilient AWS CloudOps Web Service<br>
**Owner:** Ivan Garza / DevGarza<br>
**Environment:** Controlled AWS lab in `us-east-1`<br>
**Exercise:** Nginx service interruption on one private EC2 instance<br>
**Outcome:** Recovered; replacement and survivor Healthy / InService; alarm OK

## Executive result

An application-level failure was introduced on one of two web servers behind an Application Load Balancer. The instance remained running, but the application failed target health checks. EC2 Auto Scaling consumed the ELB health result, launched a replacement, and terminated the original instance. The server in the other AZ continued answering successful requests while capacity was restored.

The complete external probe recorded **259 HTTP 200 responses and six HTTP 502 responses across 265 requests**. The **97.74% sampled success rate** includes the six failures. Successful responses were interleaved within the **19.921-second first-to-last failing request-start span**; all **204 subsequent requests returned HTTP 200** through the end of observation.

The replacement served application requests and produced access and bootstrap events in CloudWatch Logs. The alarm generated an SNS email and eventually returned to OK. The exercise demonstrated automatic recovery with a brief, measured client disruption.

## Configuration under test

| Component | Observed configuration |
| --- | --- |
| Application | Nginx on small Arm64 Amazon Linux instances |
| Entry point | Public HTTP ALB; private instance targets on port 80 |
| Placement | Private application subnets in two AZs |
| Auto Scaling | Min / desired / max `2 / 2 / 2`; EC2 and ELB health checks |
| Target health | `/health`; success 200; 15-second interval; 5-second timeout; thresholds 2 / 2 |
| Startup configuration | Group explicitly selected launch-template version 2 |
| Notification | Minimum HealthyHostCount below 2; one 1-minute period; SNS on ALARM |
| Logs | Access, error, and bootstrap paths configured; seven-day group retention |

## Measured client impact

| Measurement | Result |
| --- | ---: |
| Observation span, first to last request start | 587.127 seconds |
| Total sampled requests | 265 |
| HTTP 200 | 259 — 97.74% |
| HTTP 502 | 6 — 2.26% |
| Requests with no HTTP response | 0 |
| First-to-last failing request-start span | 19.921 seconds |
| Successful requests inside that span | 4 |
| Longest consecutive failure sequence | 2 sampled requests |
| Successful samples after the final error | 204 / 204 |
| Successful-request median / p95 duration | 176 ms / 385 ms |
| Successful-request maximum duration | 1,167 ms |

Request durations include the observer, network, load balancer, and application path. They do not isolate Nginx processing. The p95 is the nearest-rank 95th percentile of the 259 successful durations.

The first-to-last error span is an observation window, not continuous downtime: four successful responses occurred between those failing samples. The result is not a production SLA or a claim of zero downtime.

## Backend continuity

| Backend role | Placement | HTTP 200 responses |
| --- | --- | ---: |
| Original affected server | AZ A | 25 |
| Surviving server | AZ B | 182 |
| Replacement server | AZ A | 52 |

The six error responses contained no backend identity. Public evidence uses role aliases in place of original instance IDs and hostnames. The replacement's first observed successful response bounds when it could serve a successful request; it does not identify the exact moment it became ready.

## Observed sequence

1. **Baseline:** two healthy targets and an OK alarm; successful responses from both original servers.
2. **Application failure:** Nginx was interrupted on one server. Target health fell to one Healthy and one Unhealthy while EC2 status checks still showed the original instance running.
3. **Client impact:** the observer received six intermittent HTTP 502 responses. The surviving backend also returned successful responses during this interval.
4. **Routing recovery:** the first successful sample after the final error was followed by 204 successful samples through the end of monitoring. This occurred before full two-target capacity was restored.
5. **Instance replacement:** ASG Activity explicitly recorded an ELB health-check failure as the cause for taking the original instance out of service. A replacement launched; the old target entered draining during the transition.
6. **Notification:** CloudWatch entered ALARM and an SNS email was received. The notification and replacement paths operated independently.
7. **Replacement bootstrap:** new access and bootstrap log streams contained events; the replacement later appeared in successful client responses.
8. **Final state:** two targets were Healthy, both ASG instances were Healthy / InService, the original termination activity completed successfully, and the alarm showed OK.

Completion of the replacement's EC2 launch activity did not by itself establish application readiness. Similarly, the original termination activity's duration was not the duration of the client disruption.

## Cause and recovery assessment

**Introduced failure:** interruption of the Nginx service on one application instance in a planned exercise.

**Verified replacement cause:** ELB health-check failure, explicitly recorded in ASG Activity. The target health signal drove replacement; the HealthyHostCount alarm provided operator notification and did not trigger the replacement.

**Likely reason for the 502s:** requests reached the failing application while health checks and routing converged. Target connection resets are one documented ALB 502 cause. The sequence is consistent with the injected service failure, but retained ALB access logs and matching error counters were unavailable. The exact connection event therefore remains unconfirmed.

**Replacement setup:** the ASG was pinned to the updated numeric template before replacement. New application responses and access/bootstrap log events corroborate successful setup. The per-instance template version label was cropped in the retained instance-row view, so it was not independently readable. The surviving original server retained its earlier launch configuration and had its agent configured separately.

## Evidence and limits

- The [published CSV](../../evidence/recovery-observations.csv) contains every original observation, with elapsed starts and role aliases. Recalculate the [summary](../../evidence/recovery-summary.json) using [the analyzer](../../scripts/analyze_recovery.py).
- The observer slept approximately two seconds after each completed request. It did not continuously observe availability or generate a fixed-rate load test.
- The exact fault-injection marker was not captured. Exact fault-to-recovery duration and MTTR cannot be calculated.
- Metric graphs use minute-resolution buckets, and the exact ALARM-to-OK transition was not retained as text.
- Access and bootstrap events were observed for the replacement. A delivered error-log event was not separately demonstrated.
- This was one controlled application failure, not a full-AZ failure, a production traffic test, or proof that all failure modes are covered.
- The single NAT gateway and HTTP-only application remain explicit design limitations.

## Improvements informed by the exercise

For a future test, record a precise fault marker on the observer's elapsed timeline, preserve ALB error metrics or access logs for 502 attribution, and distinguish initial readiness from instance launch completion. Review health detection and bootstrap dependencies before changing thresholds; the present data do not prove that a particular tuning change would eliminate every transient error.

**Result:** automated replacement, notification, and replacement log delivery were demonstrated. Client impact remains accurately recorded: six transient HTTP 502 responses, followed by 204 consecutive successful observations and a healthy final state.

References: [ASG health checks](https://docs.aws.amazon.com/autoscaling/ec2/userguide/health-checks-overview.html), [ALB troubleshooting](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-troubleshooting.html#http-502-issues), [updating ASG launch configuration](https://docs.aws.amazon.com/autoscaling/ec2/userguide/update-auto-scaling-group.html).
