# Deployment Strategy

## Environments
- `local`: development with mock or local dependencies
- `staging`: integration and UAT
- `production`: customer-facing

## Delivery Model
- build once, promote artifacts between environments where practical
- run schema migrations before app rollout when backward compatible
- deploy API and worker services independently
- separate worker pools for chart jobs, reports, and AI workloads

## Infrastructure Components
- managed relational database
- object storage
- queue or broker
- secrets manager
- observability stack
- web app hosting and CDN

## CI/CD Stages
1. lint and static checks
2. unit and integration tests
3. build artifacts
4. deploy to staging
5. smoke tests
6. promote to production

## Secrets And Config
- environment variables validated against schema
- secrets never stored in repo
- separate credentials per environment
- rotate LLM and notification keys regularly

## Backup And Recovery
- daily database backups
- versioned object storage
- documented restore drills
- queued job replay procedures where safe

## Scaling
- scale API horizontally behind load balancer
- scale workers by queue depth
- isolate expensive AI and PDF jobs in dedicated pools

## Rollback
- support application rollback independent of migrations
- keep prior report template versions accessible
- guard deterministic engine upgrades with staged rollout and shadow validation
