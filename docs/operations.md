# Operations runbook

## Operating model

Use the ALB endpoint for public application checks and Systems Manager Session Manager for instance administration. Resolve an issue from observed application, target, instance, and logging evidence before changing infrastructure.

The commands below are an operational procedure. The [incident report](incidents/recovery-incident.md) identifies the exercise that was actually performed; the runbook does not imply that every diagnostic command was executed during that exercise.

## Baseline verification

| Layer | Check | Expected evidence |
| --- | --- | --- |
| Public application | HTTP GET `/` through the ALB | HTTP 200; expected page; backend identity |
| Health endpoint | HTTP GET `/health` | HTTP 200 and `OK` |
| Target group | Inspect registered targets | Two Healthy targets across the intended AZs |
| ASG | Inspect desired capacity, instances, and Activity | Desired 2; two Healthy, InService instances; no unresolved launch activity |
| Administration | Open Session Manager | Session opens without an inbound SSH rule |
| Monitoring | Inspect HealthyHostCount alarm | OK when the group is healthy |
| Logs | Inspect per-instance streams | Access and bootstrap events arrive |

On an instance, inspect the service without changing it:

```bash
sudo systemctl status nginx --no-pager
curl --fail --show-error http://127.0.0.1/health
sudo nginx -t
sudo tail -n 60 /var/log/cloud-init-output.log
sudo tail -n 30 /var/log/nginx/error.log
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a status
```

## Application unavailable through the ALB

1. Record the client HTTP status and whether failure is intermittent or consistent. An HTTP 502, HTTP 503, and a network timeout are different observations.
2. Inspect target health and the specific reason code. Confirm the target port, protocol, health path, and success code.
3. Check Nginx locally through Session Manager. A Running EC2 state does not prove that Nginx is listening or responding.
4. If local HTTP succeeds, inspect the web group's inbound source and the ALB group's outbound destination. Confirm both groups belong to the intended VPC.
5. If the application failed during bootstrap, read the cloud-init output before modifying the launch template. Check package installation, Parameter Store access, and the agent configuration step.
6. Restore the smallest relevant configuration or allow the configured ASG replacement to complete, then repeat the public and local health checks.

Do not infer a specific connection failure from a client HTTP 502 alone. Correlate ALB error metrics and access logs when they are available. The recorded exercise did not retain those data, so its exact 502 connection cause remains a hypothesis.

## Instance fails to become a managed node

Verify the instance profile, SSM agent state, DNS and outbound HTTPS access, and the private subnet's route to the NAT gateway. Confirm the NAT is Available and its public subnet routes to the internet gateway. An attached role and an installed agent are both required for the intended management path.

The build uses NAT egress for service endpoints. No interface VPC endpoints were deployed. Avoid adding an SSH rule as a substitute for diagnosing the management path.

## Logs missing from CloudWatch

Check the following in order:

1. The log group exists in `us-east-1` and matches the configured name.
2. Parameter `AmazonCloudWatch-dg-p1-web` contains the [published agent JSON](../config/cloudwatch-agent.json).
3. The instance role can retrieve that parameter and write to the intended log groups.
4. The agent is running and its configuration validation succeeded.
5. The source file exists, is readable, and has a new event to publish.
6. Outbound HTTPS, routing, and name resolution work.

Useful diagnostic files:

```bash
sudo tail -n 80 /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log
sudo tail -n 80 /opt/aws/amazon-cloudwatch-agent/logs/configuration-validation.log
```

After correcting the source configuration or permission, reload the parameter explicitly:

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -c ssm:AmazonCloudWatch-dg-p1-web -s
```

The configuration does not set a timestamp parser for imported file content. A CloudWatch event timestamp may therefore reflect collection rather than the original event's occurrence. Treat log-body timestamps and stream metadata according to their actual meaning.

## Alarm remains in ALARM after service recovery

Inspect the actual metric datapoints and evaluation period. Confirm the alarm dimensions include the intended ALB and target group, without an unintended AZ dimension. Verify both targets are Healthy and allow fresh metric/evaluation data to arrive. Do not replace the observed alarm state with an assumption based only on the browser page loading.

The recovery exercise ultimately showed OK. It did not capture the exact recovery state-transition timestamp, and no SNS action was configured for the OK state.

## Controlled application-failure exercise

This procedure deliberately interrupts one application server. Use a synthetic lab with two healthy targets, functioning access to the surviving instance, a confirmed SNS subscription, and an external observer. Do not run it against an unrelated workload.

1. Record baseline target health, the selected ASG template version, instance roles, and alarm state.
2. Start the observer against the ALB homepage. The reusable [PowerShell probe](../scripts/recovery-probe.ps1) accepts the target URL and records elapsed measurements.
3. Open Session Manager on only one target. Record the observer's elapsed value at fault injection if exact recovery duration is required.
4. Stop the web service on that target:

   ```bash
   sudo systemctl stop nginx
   ```

5. Observe health-check failure, routing behavior, ASG Activity, the alarm state, and actual SNS delivery. Do not manually terminate the instance to substitute for testing ELB-driven replacement.
6. Observe the new instance's bootstrap/access streams, a successful response identifying the replacement, two Healthy targets, and the alarm returning to OK.
7. Stop the observer and preserve its full output, including failed requests. Identify which observations are client samples, metric buckets, lifecycle activity, or configuration facts.

The public probe is a parameterized adaptation of the observer used for the recorded exercise. Its syntax and supporting analysis were reviewed locally; this adapted script has not been run against AWS as part of this release. The supplied evidence came from the original Windows observer.

## Audit and configuration checks

For an audit check, make a harmless metadata change on a project resource and locate the corresponding CloudTrail management event in a delivered S3 log. Compare action, resource, success, and identity metadata. For configuration checks, inspect the actual evaluated resource rows under each Config rule. Rule existence alone is not compliance proof.

For any unexpected noncompliance, inspect the resource before changing it. Record the exact condition and evaluate whether it is part of this project's intended scope. No automatic Config remediation is configured.
