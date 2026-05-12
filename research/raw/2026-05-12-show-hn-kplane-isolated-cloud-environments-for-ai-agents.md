# Show HN: Kplane – Isolated cloud environments for AI agents

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 17:18:48 +0000
- URL: https://www.kplane.dev/
- Domain: kplane.dev
- Tags: builders, tools, indie

## Feed summary

Article URL: https://www.kplane.dev/
Comments URL: https://news.ycombinator.com/item?id=48111269
Points: 1
# Comments: 0

## Extracted article text

It's a
cluster f*ck
Run thousands of Kubernetes control planes on a single shared API server, megabytes of memory overhead per control plane.
$brew tap kplane-dev/tap$brew install kplane
What it is
A normal Kubernetes cluster gives you one control plane. kplane gives you as many as you want, each with its own RBAC, CRDs, and etcd path, running on infrastructure you already have.
Why
Built for density, isolation,
and speed.
Three primitives doing the heavy lifting so platform teams can stop pretending one cluster is enough.
Shared core architecture.
Single apiserver, shared storage, per-cluster isolation. Every plane runs lightweight without duplicating infrastructure.
Multi-cluster aware.
Controllers share caches and informers across clusters. No redundant watches, no wasted memory, no duplicated work.
Built-in governance.
CRD-backed policies with native RBAC inside each plane. Fine-grained access control at every boundary.
How it works
One server routes to many planes.
Every request is scoped to a cluster path. kplane enforces RBAC, admission, and storage boundaries before the request ever touches shared state.
- rbac
- crds
- etcd path
- rbac
- crds
- etcd path
- rbac
- crds
- etcd path
- rbac
- crds
- etcd path
Quick start
Make a cluster. Throw it away.
Four commands. No accounts, no cloud, no YAML to copy. Planes are cheap, create them freely.
# install$brew install kplane-dev/tap/kplane
# create a control plane$kplane create team-alpha✔ team-alpha ready (2.8 MB, 47 ms)
# use it with kubectl$kplane use team-alpha$kubectl get nsNAME STATUS AGEdefault Active 3skube-system Active 3s
# throw it away$kplane delete team-alpha
It's Open Source. Go look at it.
Check it out on Github, read the code, file an issue, send a PR. Or just star it so you remember we exist.
