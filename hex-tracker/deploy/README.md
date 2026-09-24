# Deploying Hex Tracker to AWS

A proof-of-concept deployment: one EC2 instance running Postgres, the app,
and Caddy (TLS termination + reverse proxy) via Docker Compose — see
[docker-compose.prod.yaml](docker-compose.prod.yaml). No managed database,
no auto-scaling, no load balancer. Good enough to have a real HTTPS URL to
hand someone; not how you'd run this at real scale.

## Deploy

1. Create the stack (fill in your own IP for `SshCidr`):

   ```sh
   aws cloudformation create-stack \
     --stack-name hex-tracker \
     --template-body file://cloudformation.yaml \
     --parameters \
       ParameterKey=VpcId,ParameterValue=<default-vpc-id> \
       ParameterKey=SubnetId,ParameterValue=<a-subnet-in-that-vpc> \
       ParameterKey=SshCidr,ParameterValue=<your-ip>/32 \
     --region us-west-1

   aws cloudformation wait stack-create-complete --stack-name hex-tracker --region us-west-1
   ```

   This boots the instance, installs Docker, clones the repo, and brings up
   `db` + `app` — but not `caddy` yet, since it needs a domain to request a
   TLS certificate for, and that domain (derived from the instance's own
   Elastic IP) doesn't exist until this step finishes.

2. Read the stack's outputs, fetch the SSH key CloudFormation generated and
   stored in SSM (not a local `.pem` file you'd have to manage), and finish
   the Caddy setup:

   ```sh
   aws cloudformation describe-stacks --stack-name hex-tracker --region us-west-1 \
     --query 'Stacks[0].Outputs' --output table

   aws ssm get-parameter --name <SshKeyParameter output> --with-decryption \
     --query Parameter.Value --output text --region us-west-1 > key.pem
   chmod 400 key.pem

   ssh -i key.pem ubuntu@<PublicIp output>
   # on the instance:
   cd datatalks/hex-tracker/deploy
   echo "DOMAIN=<SslipDomain output>" > .env
   docker compose -f docker-compose.prod.yaml up -d caddy
   ```

3. Visit `https://<SslipDomain output>` — Caddy requests the cert on first
   request, so the very first load takes a few extra seconds.

## Redeploying a change

By hand:

```sh
ssh -i key.pem ubuntu@<PublicIp>
cd datatalks/hex-tracker && git pull
cd deploy && docker compose -f docker-compose.prod.yaml up -d --build
```

Or automatically — see [CI/CD](#cicd) below.

## CI/CD

[../../.github/workflows/hex-tracker-ci.yml](../../.github/workflows/hex-tracker-ci.yml)
runs on every push and PR touching `hex-tracker/**`:

1. `backend-tests` and `frontend-tests` run in parallel (pytest; lint,
   vitest, and a production build for the frontend).
2. `e2e-tests` builds and starts [docker-compose.yaml](../docker-compose.yaml)
   (the app + Postgres, not the AWS deployment) and runs the Playwright
   suite from [../e2e](../e2e) against it.
3. `deploy` — pushes to `main` only, after the above pass — assumes an
   AWS IAM role via GitHub's OIDC provider (no AWS credentials stored in
   GitHub at all) and runs the redeploy command on the EC2 instance via
   **SSM Run Command**, not SSH: no private key touches CI either. It
   looks up the instance id and domain from the CloudFormation stack's
   outputs at run time, so nothing about the current instance is
   hardcoded in the workflow. Finishes by hitting the real
   `https://<domain>/health` endpoint to confirm the deploy actually
   worked, not just that the command finished.

The `cloudformation.yaml` in this directory provisions the OIDC provider
and the deploy role itself (`GitHubOidcProvider`, `GitHubActionsDeployRole`)
— nothing to set up by hand in AWS's IAM console. After creating or
updating the stack, set its `GitHubActionsRoleArn` output as the
`AWS_DEPLOY_ROLE_ARN` secret on the GitHub repo:

```sh
gh secret set AWS_DEPLOY_ROLE_ARN --repo <owner>/<repo> --body "<GitHubActionsRoleArn output>"
```

The deploy role's trust policy only allows `sts:AssumeRoleWithWebIdentity`
for workflow runs triggered by a push to `main` in this exact repo — not
other branches, not pull requests (including from forks), not other repos.

## Clean up

Stop paying for it the moment you're done:

```sh
aws cloudformation delete-stack --stack-name hex-tracker --region us-west-1
aws cloudformation wait stack-delete-complete --stack-name hex-tracker --region us-west-1
rm -f key.pem   # local private key copy, now useless
```

This deletes the instance, its Elastic IP, the security group, and the
CloudFormation-managed key pair (SSM parameter included) — nothing about
this deployment lives outside the stack.
