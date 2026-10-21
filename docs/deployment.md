# Console deployment guide

## Preconditions and configuration

Use a dedicated AWS lab environment with permission to manage the listed resources. This procedure creates billable resources. Review the [cost model](costs.md) before provisioning. Select `us-east-1` for the workload; generated resource IDs and bucket names will differ between deployments.

This is a console deployment guide. The repository does not contain a completed Terraform implementation or a one-command infrastructure deployment.

| Name | Value |
| --- | --- |
| VPC | `dg-p1-vpc` / `10.20.0.0/16` |
| ALB / web security groups | `dg-p1-alb-sg` / `dg-p1-web-sg` |
| EC2 IAM role | `dg-p1-ec2-role` |
| Launch template | `dg-p1-web-lt` |
| Target group / ALB / ASG | `dg-p1-web-tg` / `dg-p1-alb` / `dg-p1-asg` |
| Agent parameter | `AmazonCloudWatch-dg-p1-web` |
| Alarm / SNS topic | `dg-p1-healthy-hosts-below-2` / `dg-p1-alerts` |
| Audit trail | `dg-p1-audit` |

## 1. Build the network

Create the VPC and four subnets from the [network table](architecture.md#network-layout). Attach an internet gateway. Associate the two public subnets with a route table containing `0.0.0.0/0 → internet gateway`.

Create one **public** NAT gateway in Public A with an Elastic IP. Wait for it to be Available. Add `0.0.0.0/0 → NAT gateway` to both private route tables and associate each with its intended private subnet. Keep the VPC-local route.

Verify the subnet associations and route targets explicitly. The NAT's public-subnet placement and internet gateway route are required for the intended outbound path. Record the single-NAT dependency as a design tradeoff.

## 2. Create the security groups

Create both groups in the project VPC and apply the [rule table](architecture.md#security-group-relationships). Set the web inbound source to the ALB security group. Set the ALB outbound destination to the web security group. Configure only the listed web egress ports, and verify no SSH rule was added.

## 3. Prepare logging and IAM before launching instances

Create these CloudWatch log groups with seven-day retention:

| Log group | Source file |
| --- | --- |
| `/devgarza/project1/nginx-access` | `/var/log/nginx/access.log` |
| `/devgarza/project1/nginx-error` | `/var/log/nginx/error.log` |
| `/devgarza/project1/bootstrap` | `/var/log/cloud-init-output.log` |

Store the contents of [cloudwatch-agent.json](../config/cloudwatch-agent.json) in Systems Manager Parameter Store as a Standard **String** parameter named `AmazonCloudWatch-dg-p1-web`. Keep the parameter in the workload Region.

Create an EC2 service role using [the trust policy](../iam/ec2-assume-role.json), and attach `AmazonSSMManagedInstanceCore`. Prepare the [logging policy template](../iam/cloudwatch-logs-policy.template.json) by replacing `ACCOUNT_ID` with your account ID, then attach it as the inline policy `dg-p1-cloudwatch-logs`.

The standard SSM policy includes permission to read parameters. The custom logging policy permits stream operations within the three pre-created log groups. It does not create arbitrary log groups. See [security boundaries](security-and-audit.md#instance-identity-and-logging-permissions) for the managed-policy tradeoff.

## 4. Create the launch template

Use an Amazon Linux AMI with Arm64 architecture and `t4g.micro`. Configure:

- No key pair; the EC2 role prepared above.
- The project web security group; no fixed subnet in the template.
- Public IPv4 assignment disabled.
- Encrypted 8 GiB gp3 root volume; delete on termination enabled.
- Standard CPU credits and IMDSv2 required.
- [bootstrap.sh](../scripts/bootstrap.sh) as user data.

The template used for the replacement exercise was explicitly selected as numeric version **2** on the ASG. A new deployment can have a different numeric version; select the version containing both the application and agent setup. Do not assume that changing a template's default version updates an ASG pinned to another version.

The AMI, role, log groups, Parameter Store value, outbound routing, and security groups must be ready before the first launch. The script uses `set -e`; a failure to install or configure the agent prevents subsequent application setup. Inspect bootstrap logs when diagnosing startup.

## 5. Configure the target group and ALB

Create an instance target group in the project VPC using HTTP port 80. Set `/health`, success code 200, a 15-second interval, a 5-second timeout, and healthy/unhealthy thresholds of 2.

Create an internet-facing IPv4 ALB across the two public subnets. Attach `dg-p1-alb-sg`. Configure its HTTP port-80 listener to forward all requests to the project target group. No HTTPS listener, certificate, or custom domain is included in this release.

## 6. Launch the Auto Scaling group

Create the ASG from the selected template version. Choose the two private subnets and attach the target group. Enable **ELB health checks** in addition to EC2 health checks. Set a 600-second startup grace period and minimum / desired / maximum capacity to `2 / 2 / 2`.

Allow bootstrap to complete, then verify two InService, Healthy instances and two Healthy application targets. The fixed maximum is a deliberate baseline for the exercise; do not configure a demand-based scaling policy while leaving maximum capacity at 2 and claim that load growth has been tested.

## 7. Validate application, administration, and log delivery

Use the ALB DNS name assigned to this deployment:

```bash
curl --fail --show-error http://YOUR_ALB_DNS/
curl --fail --show-error http://YOUR_ALB_DNS/health
```

Confirm the homepage identifies its backend and `/health` returns `OK`. Through Session Manager, run the checks in the [operations runbook](operations.md#baseline-verification). Verify per-instance access and bootstrap streams in CloudWatch Logs. An empty error log is not proof that an error event was delivered.

## 8. Configure health notification

Create an SNS topic and subscribe the operator's email address. Confirm the subscription. Create a CloudWatch alarm using:

| Alarm field | Setting |
| --- | --- |
| Namespace / metric | `AWS/ApplicationELB` / `HealthyHostCount` |
| Dimensions | Project ALB and target group, without an AZ dimension |
| Statistic / period | Minimum / 1 minute |
| Threshold / evaluation | Below 2 / 1 of 1 datapoints |
| Missing data | Missing |
| ALARM action | Publish to `dg-p1-alerts` |
| OK action | None in the observed build |

Verify the alarm is OK at baseline. Test actual delivery during the controlled recovery exercise; a confirmed subscription alone does not establish that an alarm notification was received.

## 9. Add management-event auditing

Create `dg-p1-audit` through CloudTrail with multi-Region coverage, read and write management events, S3 delivery, and log-file validation enabled. The observed trail uses SSE-S3 rather than a customer-managed KMS key. Additional CloudWatch Logs delivery and per-file SNS notifications are disabled.

Keep data, network-activity, and Insights event collection outside this trail's intended scope. Review the final event selectors explicitly. Generate a harmless tag change on a project instance, retrieve a delivered S3 log, and match its action, target, and successful response. [The normalized audit extract](../evidence/audit-event.json) records the verified outcome.

## 10. Add limited configuration checks

In AWS Config, use the manual setup in the workload Region. Record `AWS::EC2::SecurityGroup` and `AWS::EC2::Volume` continuously. Include `AWS::Config::ResourceCompliance` for compliance reporting. Use the AWS Config service-linked role and a dedicated S3 delivery bucket. A 30-day Config retention setting is the lab target; independently verify the saved setting.

Add `restricted-ssh` and `encrypted-volumes`, leaving the optional `kmsId` parameter blank. Both rules evaluate configuration; they do not automatically remediate violations. Verify actual resource rows, not only the existence of rule names.

The observed results show four compliant security groups, including the project pair, and two compliant EBS volumes. The added compliance-recording type and final retention setting were requested but were not visible in the retained settings screenshots; they are not claimed as independently verified. See [the evidence boundaries](security-and-audit.md#aws-config).

## Acceptance evidence

1. The public ALB returns the expected homepage and health response.
2. Both private application targets are Healthy and both ASG instances are InService.
3. Session Manager access and instance-role credentials support administration without inbound SSH.
4. Access/bootstrap events reach CloudWatch; the configured error-log path is documented separately from observed events.
5. The controlled service failure produces an explainable request sample, replacement activity, and an actual SNS alarm notification.
6. The replacement serves requests, two healthy targets are restored, and the alarm returns to OK.
7. CloudTrail delivers a matching successful management event, and Config returns resource-level compliance results.

Budget alert configuration and delivery remain an open verification item in this release. See [costs](costs.md) and the [recorded incident](incidents/recovery-incident.md).
