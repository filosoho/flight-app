# Kubernetes Configuration

This directory contains the Kubernetes configuration for the Flight App.

The project uses **Kustomize** to maintain a shared Kubernetes base and separate
environment-specific overlays for development and production.

## Directory Structure

```text
k8s/
├── base/
│   ├── flight-app-deployment.yaml
│   ├── flight-app-service.yaml
│   ├── kustomization.yaml
│   ├── postgres-deployment.yaml
│   ├── postgres-pvc.yaml
│   └── postgres-service.yaml
├── examples/
│   ├── flight-app-secret.example.yaml
│   └── postgres-secret.example.yaml
├── overlays/
│   ├── dev/
│   │   ├── flight-app-config.yaml
│   │   ├── flight-app-secret.yaml
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   └── postgres-secret.yaml
│   └── prod/
│       ├── flight-app-config.yaml
│       ├── flight-app-secret.yaml
│       ├── kustomization.yaml
│       ├── namespace.yaml
│       └── postgres-secret.yaml
└── README.md
```

> Secret files are environment-specific and are intentionally excluded from Git.
> Example secret files are provided in `k8s/examples/`.

---

## Architecture

The Kubernetes configuration is split into two layers.

### Base

The `base/` directory contains resources shared by all environments:

- Flask application Deployment
- Flask application Service
- PostgreSQL Deployment
- PostgreSQL Service
- PostgreSQL PersistentVolumeClaim
- Base Kustomization configuration

The base does not define an environment-specific namespace or application
image tag.

### Overlays

The `overlays/` directory contains environment-specific configuration.

```text
base
 │
 ├── dev overlay  → flight-app-dev
 │
 └── prod overlay → flight-app-prod
```

Each overlay provides:

- Namespace
- Application configuration
- Application secrets
- PostgreSQL secrets
- Environment-specific image tag
- Kustomization configuration

This allows the same base manifests to be reused without duplicating the
Kubernetes resource definitions.

---

## Environments

### Development

Namespace:

```text
flight-app-dev
```

The development environment currently contains the populated Flight App
database.

Database contents:

```text
flights  → 2450
states   → 50
tickets  → 13
users    → 3
```

### Production

Namespace:

```text
flight-app-prod
```

Production uses its own PostgreSQL instance and its own PersistentVolumeClaim.

The production database is intentionally separate from development and is
currently empty.

---

## Persistent Storage

PostgreSQL uses a PersistentVolumeClaim:

```text
postgres-pvc
```

The PVC requests:

```text
1Gi
```

Although both environments use the same PVC name, the resources are isolated
by namespace:

```text
flight-app-dev/postgres-pvc
flight-app-prod/postgres-pvc
```

These are separate PVC resources backed by separate persistent volumes.

This means deleting and recreating a PostgreSQL pod does not delete the database
data.

---

## Secrets

Secrets are stored in environment-specific files:

```text
overlays/dev/flight-app-secret.yaml
overlays/dev/postgres-secret.yaml

overlays/prod/flight-app-secret.yaml
overlays/prod/postgres-secret.yaml
```

These files are ignored by Git.

Only the example files are committed:

```text
examples/flight-app-secret.example.yaml
examples/postgres-secret.example.yaml
```

The application uses:

```text
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD
SECRET_KEY
```

PostgreSQL uses:

```text
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

For the current setup, `DB_PASSWORD` and `POSTGRES_PASSWORD` contain the same
password because the Flask application connects using the PostgreSQL `postgres`
user.

---

## Kustomize

The base can be rendered with:

```bash
kubectl kustomize k8s/base
```

The development environment can be rendered with:

```bash
kubectl kustomize k8s/overlays/dev
```

The production environment can be rendered with:

```bash
kubectl kustomize k8s/overlays/prod
```

Rendering the manifests before applying them is useful for checking the final
configuration.

### Environment-specific image versions

The base defines the image without an environment-specific tag:

```yaml
image: filosoho/flight-app
```

Each overlay defines the version it should use.

For example:

```yaml
images:
  - name: filosoho/flight-app
    newTag: 0.1.3
```

This allows development and production to use different application versions
without changing the shared base.

For example:

```text
base
└── filosoho/flight-app

dev
└── filosoho/flight-app:0.1.4

prod
└── filosoho/flight-app:0.1.3
```

To verify the resolved image:

```bash
kubectl kustomize k8s/overlays/dev | grep 'image:'
kubectl kustomize k8s/overlays/prod | grep 'image:'
```

---

## Deploying Development

Apply the complete development environment:

```bash
kubectl apply -k k8s/overlays/dev
```

Check the resources:

```bash
kubectl get all -n flight-app-dev
```

Check persistent storage:

```bash
kubectl get pvc -n flight-app-dev
```

Check the pods:

```bash
kubectl get pods -n flight-app-dev
```

### Accessing the development application

Forward the Flask service to localhost:

```bash
kubectl port-forward service/flight-app-service 5000:5000 \
  -n flight-app-dev
```

The application is then available at:

```text
http://localhost:5000
```

---

## Deploying Production

Apply the complete production environment:

```bash
kubectl apply -k k8s/overlays/prod
```

Check the resources:

```bash
kubectl get all -n flight-app-prod
```

Check persistent storage:

```bash
kubectl get pvc -n flight-app-prod
```

Check the pods:

```bash
kubectl get pods -n flight-app-prod
```

### Accessing the production application

Forward the Flask service to a different local port:

```bash
kubectl port-forward service/flight-app-service 5001:5000 \
  -n flight-app-prod
```

The application is then available at:

```text
http://localhost:5001
```

Using different local ports allows both environments to be accessed
independently.

---

## Health Checks

The Flask application exposes:

```text
/health
```

Kubernetes uses this endpoint for both liveness and readiness probes.

### Liveness

The liveness probe checks whether the application is still running:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 10
  periodSeconds: 20
```

### Readiness

The readiness probe checks whether the application is ready to receive traffic:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 5
  periodSeconds: 10
```

A pod that is not ready is not considered available by Kubernetes Services.

---

## Useful Commands

### View all resources in an environment

```bash
kubectl get all -n flight-app-dev
kubectl get all -n flight-app-prod
```

### View pod status

```bash
kubectl get pods -n flight-app-dev
kubectl get pods -n flight-app-prod
```

### View application logs

```bash
kubectl logs deployment/flight-app -n flight-app-dev
kubectl logs deployment/flight-app -n flight-app-prod
```

### View PostgreSQL logs

```bash
kubectl logs deployment/postgres -n flight-app-dev
kubectl logs deployment/postgres -n flight-app-prod
```

### Inspect a deployment

```bash
kubectl describe deployment flight-app -n flight-app-dev
```

### Restart the application

```bash
kubectl rollout restart deployment/flight-app \
  -n flight-app-dev
```

For production:

```bash
kubectl rollout restart deployment/flight-app \
  -n flight-app-prod
```

### Check rollout status

```bash
kubectl rollout status deployment/flight-app \
  -n flight-app-dev
```

---

## Database Access

Connect to the development database:

```bash
kubectl exec -it deployment/postgres \
  -n flight-app-dev \
  -- psql -U postgres -d flight_db
```

Connect to the production database:

```bash
kubectl exec -it deployment/postgres \
  -n flight-app-prod \
  -- psql -U postgres -d flight_db
```

The databases are independent because each environment has its own PostgreSQL
Deployment and PersistentVolumeClaim.

---

## Important Notes

### Do not commit secrets

Never commit:

```text
*-secret.yaml
```

The repository should contain only example secret files.

Verify that a secret file is ignored with:

```bash
git check-ignore -v k8s/overlays/dev/flight-app-secret.yaml
```

### Do not apply the base directly

The base does not contain environment-specific configuration.

Use an overlay:

```bash
kubectl apply -k k8s/overlays/dev
```

or:

```bash
kubectl apply -k k8s/overlays/prod
```

### Review before applying

Render an overlay first:

```bash
kubectl kustomize k8s/overlays/prod
```

This makes it possible to inspect the final Kubernetes configuration before
changing the cluster.
