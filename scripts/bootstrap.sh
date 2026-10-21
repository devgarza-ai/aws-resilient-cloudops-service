#!/bin/bash
set -e

# 1. Install the web server and logging agent on Amazon Linux.
dnf install -y nginx amazon-cloudwatch-agent

# 2. Load the shared logging configuration and start log collection.
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c ssm:AmazonCloudWatch-dg-p1-web \
  -s

# 3. Create a homepage that identifies the server answering the request.
server_name="$(hostname)"
cat > /usr/share/nginx/html/index.html <<EOF
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DevGarza CloudOps Web Service</title>
</head>
<body>
  <h1>DevGarza CloudOps Web Service</h1>
  <p>Served by: ${server_name}</p>
</body>
</html>
EOF

# 4. Create the endpoint that the load balancer will check.
printf 'OK\n' > /usr/share/nginx/html/health

# 5. Validate Nginx configuration, start it, and enable it for future boots.
nginx -t
systemctl enable --now nginx

# 6. Confirm that this server can serve the health endpoint locally.
curl --fail --silent --show-error \
  --retry 5 --retry-connrefused --retry-delay 2 \
  http://127.0.0.1/health
