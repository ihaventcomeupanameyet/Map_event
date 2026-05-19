- Deploy and Run (EC2-focused)

This document focuses on deploying the project to an AWS EC2 instance without manually SSH-ing into the machine. It assumes you will use the included user-data script `scripts/ec2-user-data.sh`, the production `Makefile` targets, or a CI-built image flow.

## What the repo provides for EC2

- `Makefile`: wraps the production compose workflow with `make prod-up`, `make prod-down`, `make prod-restart`, `make prod-logs`, `make prod-ps`, and `make prod-refresh`.
- `scripts/ec2-user-data.sh`: installs Docker and `make`, clones/updates the repo, writes an `.env` into the app dir (priority: `ENV_B64` → `ENV_PLAIN` → SSM `SSM_PARAM`), optionally logs into ECR, and runs the production Makefile targets.
  It also enables the Docker daemon and adds common EC2 login users (`ubuntu`, `ec2-user`) to the `docker` group.
- `scripts/aws-ec2-bootstrap.sh`: an alternative bootstrapper that installs system packages and configures systemd services if you prefer not to use Docker.
- `.env.production.example`: variables required for production (API keys, DB, BACKEND_URL, geocoder settings).

## Local production-mode commands

Use these from the repo root:

```bash
make prod-up
make prod-down
make prod-restart
make prod-logs
make prod-ps
make prod-refresh
```

Unlike the dev compose file, the production stack bakes code into the image. If backend code changes, use `make prod-up` or `make prod-restart` so the image is rebuilt.

## Option A — Quick deploy by embedding `.env` in user-data (fast)

Use when you need a single-step deploy and understand that user-data is visible to account admins.

Steps

1. Create a completed `.env` locally from `.env.production.example` and fill in real values.
   The production frontend proxies API calls through Next.js, so it does not need a public backend URL in the browser.
2. Encode it as base64 (single line):
   - Linux: `BASE64=$(base64 -w0 .env.production)`
   - macOS: `BASE64=$(base64 .env.production | tr -d '\n')`
3. Produce a `user-data` file that sets `ENV_B64` and appends the repo's script:

```bash
REPO_URL="https://github.com/your-org/your-repo.git"
APP_DIR="/opt/map_event_app"
COMPOSE_FILE="docker-compose.production.yml"
printf '#!/usr/bin/env bash\nENV_B64="%s"\nREPO_URL="%s"\nAPP_DIR="%s"\nCOMPOSE_FILE="%s"\n\n' \
  "$BASE64" "$REPO_URL" "$APP_DIR" "$COMPOSE_FILE" > /tmp/user-data.sh
cat scripts/ec2-user-data.sh >> /tmp/user-data.sh
chmod 600 /tmp/user-data.sh
```

4. Launch the EC2 instance with that user-data:

```bash
aws ec2 run-instances \
  --image-id ami-0123456789abcdef0 \
  --instance-type t3.small \
  --count 1 \
  --key-name my-key \
  --security-group-ids sg-01234567 \
  --subnet-id subnet-01234567 \
  --user-data file:///tmp/user-data.sh \
  --iam-instance-profile Name=EC2SSMRole \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=map-event-app}]'
```

Notes

- `ENV_B64` is decoded on boot and written to `$APP_DIR/.env` with `chmod 600`.
- The script then pulls/builds images and starts the stack.

## Option B — Production: CI → ECR → EC2 (recommended)

Flow

1. CI (e.g., GitHub Actions) builds backend/frontend images and pushes to ECR.
2. Store `.env` or just secrets in SSM Parameter Store (SecureString) or Secrets Manager.
3. Provision EC2 with an IAM instance profile that allows SSM read and ECR pulls.
4. Use a lightweight user-data: log into ECR, fetch SSM parameter into `$APP_DIR/.env`, then run `make prod-pull` and `make prod-up`.

IAM policy example (attach to instance role):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect":"Allow","Action":["ssm:GetParameter","ssm:GetParameters"],"Resource":["arn:aws:ssm:REGION:ACCOUNT_ID:parameter/map_event_app*"]},
    {"Effect":"Allow","Action":["ecr:GetAuthorizationToken","ecr:BatchGetImage","ecr:GetDownloadUrlForLayer"],"Resource":"*"}
  ]
}
```

Create an SSM parameter:

```bash
aws ssm put-parameter --name "/map_event_app/.env" \
  --value "$(cat .env.production)" \
  --type "SecureString" --overwrite
```

## Terraform example (EC2 instance with `user_data`)

```hcl
resource "aws_instance" "app" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.small"
  subnet_id     = aws_subnet.app_subnet.id
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name
  user_data = file("./user-data.sh")
  tags = { Name = "map-event-app" }
}
```

## Verify and troubleshoot

- Inspect cloud-init / user-data logs in the EC2 console system log.
- Use `aws ssm start-session --target <instance-id>` to inspect files without opening SSH.
- Confirm `$APP_DIR/.env` exists and contains expected values.
- Inspect Docker compose status:

```bash
make prod-ps
make prod-logs
```

If `docker ps` returns a socket permission error after SSH login, either run `sudo docker ps` or re-login after the bootstrap script has added your login user to the `docker` group.

Common issues

- Missing `.env`: ensure `ENV_B64` was embedded, `ENV_PLAIN` provided, or SSM parameter exists and the instance role can read it.
- Permission errors fetching SSM: attach a minimal policy with `ssm:GetParameter` and `kms:Decrypt` (if applicable) to the instance role.
- Docker run failures: check instance resources (add swap or increase instance size) and inspect `docker compose logs`.

## EBS / PostgreSQL note

For durability, store PostgreSQL data on an attached EBS volume and mount it before starting the service. The repo's `scripts/aws-ec2-bootstrap.sh` shows an example of setting PostgreSQL data directory and creating the DB user.

## Security recommendations

- Prefer SSM/Secrets Manager + instance role for secrets over embedding sensitive values in user-data.
- Restrict EC2 security group to only required ports (80/443) and avoid exposing PostgreSQL publicly.
- Use SSM Session Manager rather than opening SSH if possible.

---

If you want a ready-to-launch `/tmp/user-data.sh` that embeds your `.env.production.example` as `ENV_B64`, or a GitHub Actions workflow that pushes to ECR, tell me which and I'll prepare it.

---

If you want, I can:

- produce a ready-to-launch `/tmp/user-data.sh` that embeds your `.env.production.example` as `ENV_B64`, or
- add a GitHub Actions workflow that builds & pushes the images to ECR and an EC2 `user-data` that pulls them.

Tell me which and I will prepare the files.
