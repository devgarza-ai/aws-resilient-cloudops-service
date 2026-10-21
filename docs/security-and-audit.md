# Security and audit evidence

## Network access

Application instances run in private subnets with public IPv4 assignment disabled. Their inbound HTTP rule references the ALB security group. The ALB accepts public HTTP requests and can forward port 80 only to the web group. No inbound SSH rule or bastion is part of the build.

This is a synthetic HTTP service. The page and health endpoint do not process accounts, payment data, customer records, or other sensitive application content. Transport encryption and authentication for application users were not implemented.

## Instance identity and logging permissions

The EC2 instance profile supplies role credentials to Systems Manager and the CloudWatch agent. Access keys are not embedded in user data or repository files.

| Permission set | Purpose | Scope boundary |
| --- | --- | --- |
| EC2 trust policy | Allows EC2 to assume the instance role | Service principal `ec2.amazonaws.com` |
| `AmazonSSMManagedInstanceCore` | Managed-instance communication, Session Manager support, Parameter Store reads | AWS-managed baseline; includes actions with resource `*` |
| `dg-p1-cloudwatch-logs` | Discover log groups and write the application's log streams | Group discovery restricted to `us-east-1`; stream actions restricted to the three project groups |

The custom policy is scoped, but the role as a whole is not described as a fully minimized production IAM policy. Further narrowing of the standard SSM policy is a future hardening decision and requires preserving the management features actually used.

The [published logging template](../iam/cloudwatch-logs-policy.template.json) replaces the private account ID with `ACCOUNT_ID`. Render it for the intended account before attaching it. The agent runs as the Linux `root` user to read local log files; this operating-system identity is separate from its AWS role identity.

## Storage and metadata

The launch-template settings included encrypted gp3 root volumes, delete-on-termination, required IMDSv2, and Standard CPU credits. These were explicitly owner-confirmed during the build. Config independently reported two evaluated EBS volumes compliant with the encryption rule.

The Config result proves the rule's encryption condition for the listed resources. It does not verify volume retention behavior, all launch-template fields, or every storage setting.

## CloudTrail

Trail `dg-p1-audit` was created with multi-Region coverage and showed **Logging**. The retained setup shows all management API activity, log-file validation enabled, SSE-KMS disabled, no CloudWatch Logs integration, and no SNS log-delivery notifications. In this configuration, CloudTrail uses SSE-S3 for the log objects.

A delivered log contained 42 management events. One `CreateTags` event changed the `AuditCheck` label on the surviving application instance. The response succeeded, `readOnly` was false, and the calling IAM user's session metadata recorded MFA authentication.

The [normalized event extract](../evidence/audit-event.json) preserves those facts while removing account identifiers, principal identifiers, source addresses, tag values containing calendar data, and wall-clock timestamps. It is an extract, not an unmodified CloudTrail log.

Log-file validation being enabled is a configuration fact. Cryptographic validation of the delivered digest chain was not performed and is not claimed.

## AWS Config

| Rule | Condition checked | Observed result |
| --- | --- | --- |
| `restricted-ssh` / `INCOMING_SSH_DISABLED` | Inbound SSH is not open to `0.0.0.0/0` or `::/0` | Four security groups Compliant; includes `dg-p1-alb-sg` and `dg-p1-web-sg` |
| `encrypted-volumes` / `ENCRYPTED_VOLUMES` | Attached EBS volumes are encrypted; no specific KMS key required | Two volumes Compliant |

Both retained rule views show a successful evaluation in detective mode. No remediation action was configured. A compliant SSH rule result is narrower than a claim that a security group is secure for every use case.

The setup review records continuous recording of security groups and EBS volumes. Recording is scoped by resource type throughout the Region, not only by the project's names. Adding `AWS::Config::ResourceCompliance` and retaining data for 30 days were specified in the setup guidance; the final saved settings for those items were not independently captured. The publication therefore marks their saved state as unverified rather than extending the observed rule results.

The [normalized compliance evidence](../evidence/config-evaluations.json) includes the observed counts and the explicit verification boundaries.

## Operational verification boundaries

- Session Manager access was used successfully, but a separate Session Manager session-transcript logging destination was not demonstrated.
- Nginx access and bootstrap streams contained events for the replacement. Error-log collection was configured; a delivered error event was not separately demonstrated.
- The HealthyHostCount alarm generated an actual SNS email. No alarm recovery email was configured.
- Budget alert configuration and delivery are pending verification.
- No WAF, application TLS, security penetration test, or account-wide security certification is claimed.

References: [SSM managed policy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonSSMManagedInstanceCore.html), [CloudWatch agent configuration](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html), [CloudTrail setup](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-create-a-trail-using-the-console-first-time.html), [restricted SSH rule](https://docs.aws.amazon.com/config/latest/developerguide/restricted-ssh.html), [encrypted volume rule](https://docs.aws.amazon.com/config/latest/developerguide/encrypted-volumes.html).
