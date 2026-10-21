# Cost model

## Verification status

Project-specific infrastructure charges have not yet been isolated in the billing evidence. The retained billing view showed a training subscription and did not yet show the workload's EC2, ALB, NAT, or Config charges. Training subscriptions are not attributed to this deployment.

**Actual project spend: pending verification.**<br>
**Budget alert configuration and delivery: pending verification.**

No numeric project total, hard spending cap, free deployment, or successfully tested budget notification is claimed.

## Cost drivers

| Component | What drives cost | Design choice |
| --- | --- | --- |
| NAT gateway | Provisioned gateway hours, processed data, associated public IPv4 usage | One shared gateway rather than one per AZ |
| Application Load Balancer | Provisioned load-balancer hours, capacity usage, associated public IPv4 usage | One public ALB |
| EC2 | Instance runtime and purchasing model | Two small Arm64 instances at a fixed baseline |
| EBS | Provisioned storage and selected performance | Small gp3 root volumes |
| CloudWatch | Alarm usage, log ingestion, retention, and queries | One health alarm; three log groups; seven-day retention |
| AWS Config | Recorded configuration items and rule evaluations | Limited resource types and two managed rules |
| CloudTrail / S3 | Log delivery options, S3 requests, retained objects | Intended first copy of management events; SSE-S3; no additional log destination |
| Data transfer | Destination, volume, and cross-AZ paths | Documented cross-AZ NAT egress for the second private subnet |

The first CloudTrail management-event copy has no CloudTrail delivery charge under the documented pricing model; S3 charges still apply. Additional copies and event types have different pricing. Credits and account-specific offers can affect the bill and should not be presented as the architecture's underlying cost.

## Interpreting a future cost update

Separate recorded usage, gross service charges, credits, taxes, and any unrelated subscriptions. Identify the workload's active resources and relevant usage types before attributing an account total to the project. Billing and budget data can lag resource usage.

A budget notification is an alert, not an automatic spending cap. Until its saved thresholds, recipients, and delivery are verified, keep it listed as an open control. Do not infer that an alert was configured merely because billing access works.

## Retained design tradeoff

The single NAT gateway reduces the gateway count but does not make the lab free or provide resilient egress. The ALB and NAT remain metered while provisioned, including periods without deliberate test traffic. Their operating duration is therefore a material cost driver even for a small page.

Use current regional prices and the intended operating duration when preparing an estimate. No fixed dollar estimate is supplied without those inputs and account-specific verification.

References: [VPC pricing](https://aws.amazon.com/vpc/pricing/), [ELB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/), [EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/), [Config pricing](https://aws.amazon.com/config/pricing/), [CloudTrail pricing](https://aws.amazon.com/cloudtrail/pricing/), [AWS Budgets behavior](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).
