# Design decisions

## Private application tier behind a public ALB

**Decision:** public entry through the ALB; application instances in private subnets without public IPv4 assignment.

**Reason:** separate client entry from compute administration and keep the web security group's inbound source limited to the ALB group. Session Manager provides the administration path without opening SSH.

**Tradeoff:** instance management, package installation, and log delivery require working outbound connectivity or appropriately designed VPC endpoints.

## Two instances in two AZs, fixed desired capacity

**Decision:** ASG minimum, desired, and maximum capacity are all 2; application instances use two AZs.

**Reason:** provide a surviving server during a single-target failure and demonstrate health-driven replacement with a small baseline.

**Tradeoff:** the deployment is not configured for demand-based capacity growth. A two-AZ placement is also not proof that an AZ outage has been tested.

## One NAT gateway

**Decision:** both private subnets use a public NAT gateway in the first AZ.

**Reason:** reduce the number of continuously provisioned NAT gateways in the lab.

**Tradeoff:** outbound access depends on that AZ, and cross-AZ egress can add charges. Application placement across AZs does not remove this egress dependency. A NAT per AZ or an endpoint strategy would require a separate availability and cost evaluation.

## ELB health is enabled on the ASG

**Decision:** enable ELB health checks in addition to EC2 health, with a 600-second startup grace period.

**Reason:** the application can fail while EC2 reports a running instance. The recovery test demonstrated this distinction and showed replacement activity caused by failed ELB health.

**Tradeoff:** health-check detection, ASG decisions, provisioning, and bootstrap have independent timing. The grace period is startup protection, not a promise of application readiness or a measured recovery target.

## Shared bootstrap and logging configuration

**Decision:** install the application and agent through launch-template user data, and retrieve one shared agent configuration from Parameter Store.

**Reason:** new instances need to reconstruct the application and log pipeline rather than rely on a manual fix applied only to the original hosts.

**Tradeoff:** the bootstrap depends on package repositories, IAM, routing, and Parameter Store. Its fail-fast sequence currently makes logging setup a dependency of application setup. A prebuilt image and separate readiness instrumentation are future improvements, not completed work.

## Numeric launch-template version

**Decision:** pin the ASG to the intended numeric template version.

**Reason:** make the selected startup configuration explicit. The tested group used version 2 even though the template's default remained version 1.

**Tradeoff:** a later template version requires an intentional ASG update. Existing instances retain their original launch configuration until replaced; updating the group does not retroactively modify the surviving instance.

## Bounded monitoring and configuration scope

**Decision:** use a HealthyHostCount alarm, SNS email, three application log groups with seven-day retention, and two managed Config rules.

**Reason:** demonstrate actionable monitoring and resource-level checks without treating every AWS service as a requirement for one portfolio project.

**Tradeoff:** this is not complete application telemetry or continuous security assurance. The error-log destination is configured, but the evidence does not separately demonstrate an error event arriving. Budget alerts remain pending verification.

## Measure the failure honestly

**Decision:** preserve the complete client sample and describe its limits.

**Reason:** a surviving target and successful replacement are useful outcomes, but six client errors still occurred. The observed sampled success rate is 97.74%, followed by 204 consecutive successful samples.

**Tradeoff:** a small, sequential observer cannot establish continuous uptime, a production SLA, or load-handling capacity. The missing exact fault marker prevents an exact MTTR calculation.

## Console release before Terraform

**Decision:** make the console implementation understandable and evidence-backed before rebuilding it with Terraform.

**Reason:** the network, identity, health, and logging relationships should be explainable before they are encoded as infrastructure as code.

**Tradeoff:** this release requires a manual deployment procedure. Terraform state, drift handling, repeatable plans, and Terraform deployment automation are future scope.
