\# 🛡️ Self-Healing LLM Gateway



> \*\*An infrastructure layer that keeps LLM applications running when individual providers fail.\*\*



Modern GenAI applications often depend on a single model provider.

But providers can experience rate limits, temporary outages, latency spikes, or service failures.



This project builds a \*\*self-healing LLM gateway\*\* that sits between an application and multiple LLM providers — handling routing, caching, usage controls, failure detection, automatic failover, and observability.



\---



\## 🚨 The Problem



A typical LLM application looks like this:



```text

Application

&#x20;    │

&#x20;    ▼

&#x20; LLM API

&#x20;    │

&#x20;    ✕ Provider failure

&#x20;    │

&#x20;    ▼

Application failure



A provider failure should not necessarily become an application failure.



This gateway changes the architecture:



&#x20;                        ┌───────────────┐

&#x20;                        │  Application  │

&#x20;                        └───────┬───────┘

&#x20;                                │

&#x20;                                ▼

&#x20;                   ┌────────────────────────┐

&#x20;                   │   Self-Healing Gateway │

&#x20;                   │                        │

&#x20;                   │  Routing                │

&#x20;                   │  Rate Limits           │

&#x20;                   │  Budgets               │

&#x20;                   │  Exact Cache            │

&#x20;                   │  Semantic Cache         │

&#x20;                   │  Circuit Breakers       │

&#x20;                   │  Retry / Failover       │

&#x20;                   │  PII Redaction          │

&#x20;                   └───────────┬────────────┘

&#x20;                               │

&#x20;                ┌──────────────┼──────────────┐

&#x20;                ▼              ▼              ▼

&#x20;            Gemini       Cloudflare        Cohere

&#x20;                               │

&#x20;                               ▼

&#x20;                        Prometheus

&#x20;                               │

&#x20;                               ▼

&#x20;                            Grafana

🔄 How the Gateway Heals Itself



The important part of this project is not simply calling multiple APIs.



It is what happens when something goes wrong.



Application

&#x20;    │

&#x20;    ▼

&#x20;Gemini request

&#x20;    │

&#x20;    ✕ Failure

&#x20;    │

&#x20;    ▼

&#x20;Failure handling

&#x20;    │

&#x20;    ▼

&#x20;Provider failover

&#x20;    │

&#x20;    ▼

&#x20;Cloudflare

&#x20;    │

&#x20;    ✓ Success

&#x20;    │

&#x20;    ▼

&#x20;HTTP 200



The application can continue receiving a successful response without having to implement provider-specific recovery logic itself.



🧠 Request Lifecycle



Every request passes through a controlled pipeline:



Request

&#x20;  │

&#x20;  ▼

Authentication

&#x20;  │

&#x20;  ▼

Tenant validation

&#x20;  │

&#x20;  ▼

Rate / Budget controls

&#x20;  │

&#x20;  ▼

Model \& provider routing

&#x20;  │

&#x20;  ▼

Exact cache lookup

&#x20;  │

&#x20;  ├── HIT ──────────────► Return cached response

&#x20;  │

&#x20;  ▼

Semantic cache lookup

&#x20;  │

&#x20;  ├── HIT ──────────────► Return cached response

&#x20;  │

&#x20;  ▼

LLM Provider

&#x20;  │

&#x20;  ├── Success ──────────► Cache + Return

&#x20;  │

&#x20;  └── Failure

&#x20;         │

&#x20;         ▼

&#x20;    Retry / Recovery

&#x20;         │

&#x20;         ▼

&#x20;    Healthy Provider

&#x20;         │

&#x20;         ▼

&#x20;       Success

⚡ What It Handles

🧭 Intelligent Routing



Routes requests through the configured LLM providers and supports model-tier based request handling.



💾 Multi-Level Caching



Uses Redis for:



Exact response caching

Semantic caching

Reduced repeated provider calls

🚦 Rate Limiting



Protects the gateway from excessive request volume using Redis-backed rate control.



💰 Tenant Budgets



Tracks tenant usage and rejects requests when configured budgets are exceeded.



🔌 Circuit Breakers



Prevents repeatedly sending requests to unhealthy providers.



🔄 Failure-Only Failover



A healthy provider is not unnecessarily replaced.



Failover occurs when the current provider actually encounters a failure.



🔁 Retry \& Recovery



Transient provider failures can trigger recovery behaviour before moving to another provider.



🔐 Secure Authentication



Uses tenant-aware Bearer authentication with constant-time key comparison.



🕵️ PII Redaction



Sensitive information is removed from application logs before operational data is recorded.



📊 Observability



A self-healing system is only useful if you can see that it healed.



The gateway exposes Prometheus metrics which are visualized through Grafana.



The dashboard tracks areas such as:



Requests

&#x20;  │

&#x20;  ├── Request rate

&#x20;  ├── Successful requests

&#x20;  └── Latency



Providers

&#x20;  │

&#x20;  ├── Provider requests

&#x20;  ├── Provider failures

&#x20;  ├── Provider latency

&#x20;  └── Provider health



Self-Healing

&#x20;  │

&#x20;  ├── Provider failures

&#x20;  ├── Failovers

&#x20;  ├── Recovery success

&#x20;  └── Retry attempts



Governance

&#x20;  │

&#x20;  ├── Rate-limit rejections

&#x20;  └── Budget rejections



Caching

&#x20;  │

&#x20;  ├── Cache hits

&#x20;  └── Cache misses



Infrastructure

&#x20;  │

&#x20;  └── Redis health

🔥 Real Failure-Recovery Validation



A controlled development failure was used to verify the recovery path:



Gemini

&#x20;  │

&#x20;  ✕ Failure

&#x20;  │

&#x20;  ▼

Provider Failover

&#x20;  │

&#x20;  ▼

Cloudflare

&#x20;  │

&#x20;  ✓ Success

&#x20;  │

&#x20;  ▼

Gateway HTTP 200



The same event became visible in Grafana through:



Gemini failures

Provider failures

Provider failovers

Cloudflare fallback success

Successful gateway requests

Gateway latency

Provider latency



This demonstrates that the system is not only capable of failing over — the recovery behaviour is observable.



Failure injection is restricted to development environments and is blocked in production.



🐳 Run the Gateway

1\. Clone

git clone https://github.com/Deepthi-0411/self-healing-llm-gateway.git

cd self-healing-llm-gateway

2\. Configure environment variables



Create a .env file containing the required provider credentials and gateway configuration.



Never commit .env or expose provider/API keys.



3\. Start the infrastructure

docker compose up --build -d



The stack includes:



Gateway

&#x20;  │

&#x20;  ├── FastAPI

&#x20;  ├── LiteLLM

&#x20;  └── Application logic

&#x20;       │

&#x20;       ├── Redis

&#x20;       ├── Prometheus

&#x20;       └── Grafana



Default local endpoints:



Gateway      http://localhost:8000

Prometheus   http://localhost:9090

Grafana      http://localhost:3000

🧪 Validation



The project includes automated tests covering core gateway behaviour.



Run:



uv run python -m pytest -v



Current validation:



8 passed



The gateway was also validated for:



Authentication

Tenant authorization

Provider routing

Exact caching

Semantic caching

Rate limiting

Budget enforcement

Provider failure handling

Provider failover

Redis connectivity

Production failure-injection protection

Prometheus metrics

Grafana observability

🛠️ Technology Stack

Layer	Technology

API	FastAPI

LLM abstraction	LiteLLM

Runtime	Python

Cache \& state	Redis

Containerization	Docker / Docker Compose

Metrics	Prometheus

Visualization	Grafana

Testing	Pytest

LLM Providers

Google Gemini

Cloudflare Workers AI

Cohere

📁 Project Structure

self-healing-llm-gateway/

│

├── app/

│   ├── cache/

│   ├── gateway/

│   └── llm/

│

├── prometheus/

│

├── tests/

│

├── Dockerfile

├── docker-compose.yml

├── main.py

├── pyproject.toml

├── uv.lock

└── README.md

🎯 Engineering Goal



This project was built with an infrastructure-first mindset.



The objective was not simply to create another application that calls an LLM.



The objective was to build a layer that can:



Route requests. Protect resources. Reduce unnecessary calls. Detect failures. Recover automatically. And make the entire process observable.



That turns the LLM gateway into an infrastructure component that applications can depend on.



🚀 Future Improvements



Potential extensions include:



Distributed gateway deployment

Advanced provider health scoring

Adaptive routing based on latency and cost

Distributed tracing

More granular SLO/SLA monitoring

Automated provider recovery policies

👩‍💻 Author



Deepthi M



AI/ML • Generative AI • LLM Infrastructure • Machine Learning
