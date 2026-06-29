# Architecture

## Request flow

```mermaid
sequenceDiagram
    actor C as Client / custom messaging
    participant W as Worker (edge)
    participant Q as Queue
    participant K as Consumer
    participant T as Cloudflare Tunnel
    participant F as FastAPI (Studio)
    participant H as Hermes

    C->>W: POST /agent (X-API-Key, JWT)
    W->>W: auth + rate-limit (KV)
    W->>W: createJob (D1, status=queued)
    W->>Q: send(JobMessage)
    W-->>C: 202 {job_id, status:queued}
    Q->>K: deliver batch
    K->>K: updateJob status=running
    K->>T: POST /execute (HMAC signed)
    T->>F: forward
    F->>H: hermes chat -q
    H-->>F: response
    F-->>K: {response, exec_ms, tokens}
    K->>K: updateJob status=done (D1)
    C->>W: POST /status {job_id}
    W-->>C: job row (done + response)
```

## Components

```mermaid
flowchart LR
  subgraph Edge[Cloudflare Edge]
    W[api-worker Hono]
    KC[queue-consumer]
    D[(D1)]
    KV[(KV)]
    R2[(R2)]
    QQ[[Queue]]
  end
  subgraph Studio[Lightning Studio]
    CF[cloudflared]
    FA[FastAPI]
    HM[Hermes]
  end
  C[Client] -->|HTTPS| W
  W --> D & KV
  W --> QQ --> KC
  KC -->|HMAC| CF --> FA --> HM
  KC --> D
  FA --> R2
  W -->|signed URL| C
```

## Design decisions

- **Async-by-default for agent/deploy.** These are slow and exceed edge CPU
  limits, so they are always queued. `/chat` is also queued for uniformity
  (a sync fast-path can be added later behind a flag).
- **D1 is the source of truth for job state.** The consumer writes status
  transitions (queued→running→done/error); clients poll `/status`.
- **HMAC, not mTLS, for Worker→Studio.** Simpler to operate over a Tunnel and
  sufficient with timestamp + replay-nonce. mTLS can be layered on the Tunnel.
- **Subprocess Hermes bridge.** Decouples the API from Hermes internals and
  survives Hermes upgrades. A long-lived IPC bridge is a future optimization.
- **Streaming later.** The contract returns a Job ID + poll today; SSE/WebSocket
  streaming can be added on `/status?stream=1` without changing the data model.

## Failure handling

- Queue consumer `message.retry()` on upstream failure → Queues retries up to
  `max_retries`, then dead-letters to `terragravity-jobs-dlq`.
- Every failure path writes a `logs` row with the request UUID.
- The Worker never trusts upstream success blindly — non-2xx becomes a job error.
