# Terraform Module Split Spec

**Status:** proposed

## Problem

[`terraform/main.tf`](../../terraform/main.tf) currently couples EFS, ECS, SSM, Amplify, task definitions, and ALB wiring in one large file.

It is readable today, but it has enough unrelated concerns to make future changes riskier than they should be.

## Goal

Break the infrastructure definition into smaller modules while keeping the deployed shape and runtime behavior the same.

## In Scope

- Split network, compute, storage, and frontend wiring into separate Terraform modules or focused files.
- Keep current resources and outputs functionally equivalent.
- Preserve the runtime env wiring, including the frontend API URL and worker settings.

## Not In Scope

- Redesigning the infrastructure topology.
- Changing the deployment target or cloud provider.
- Adding new production services just because the file is being reorganized.

## Existing Building Blocks

- The current file already makes the resource boundaries visible.
- Existing environment variables and outputs can be carried into module inputs and outputs.

## Proposed Shape

- `modules/network` for VPC, subnets, security groups, and load balancer primitives.
- `modules/storage` for EFS and any persistent data wiring.
- `modules/compute` for ECS cluster, task definition, and service wiring.
- `modules/frontend` for Amplify or any web-specific deployment glue.
- Keep `main.tf` as composition only, so the root module stays readable.

## Acceptance Criteria

- `terraform plan` and `terraform validate` still succeed.
- The resource graph stays functionally equivalent.
- The root configuration reads as orchestration instead of implementation detail.

## Test Plan

- Run `terraform fmt` and `terraform validate` after the split.
- Compare plans before and after to make sure nothing structural changed unexpectedly.
- Verify the deployed env vars and outputs still match what the app expects.

## Risks

- Terraform module splits can accidentally change resource addresses and force replacements.
- A too-fine split can make the root module harder to understand if the boundary choices are arbitrary.
