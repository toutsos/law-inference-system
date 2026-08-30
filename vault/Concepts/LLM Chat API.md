# LLM Chat API

## What it is / problem it solves

The HTTP interface every modern chat LLM exposes: you POST a list of role-tagged
messages, you get back one assistant message plus accounting metadata. Ollama's
`POST /api/chat`, OpenAI's `/v1/chat/completions` and Anthropic's `/v1/messages`
are the same idea in three dialects.

**The one property that governs everything built on top of it: the endpoint is
stateless.** The server keeps no conversation, no memory, no session. Each call
is a pure function of the request body. Anything that looks like memory —
follow-up questions, an agent's scratchpad, retrieved documents — is state *your
application* holds and re-sends in full on every single call.

What the server therefore does **not** do, and what the response therefore never
contains:

| You might expect | Reality |
| --- | --- |
| The conversation so far | Lives in the **request**. You resend the whole history each call; it is not echoed back. |
| Retrieved documents / RAG chunks | The provider has no access to your database. Retrieval is your code; the chunks reach the model only as text you paste into a message. |
| Tools the model "called" | The model never executes anything. It *emits a request* to call a tool; your code runs it and sends the result back as another message. |

Request (`/api/chat`) — messages with roles:

```jsonc
{ "model": "...", "stream": false,
  "messages": [ {"role": "system", "content": "..."},
                {"role": "user",   "content": "..."} ] }
```

Response — one message plus accounting:

```jsonc
{ "model": "...", "created_at": "...",
  "message": { "role": "assistant", "content": "..." },
  "done": true,
  "done_reason": "stop",          // or "length" — see below
  "prompt_eval_count": 26,        // tokens IN
  "eval_count": 282,              // tokens OUT
  "total_duration": 4883583458,   // nanoseconds
  "load_duration": 1334875,
  "prompt_eval_duration": 342546000,
  "eval_duration": 4535599000 }
```

Two fields that matter more than they look:

- **`done_reason`** — `"stop"` means the model finished its thought; `"length"`
  means it hit the token ceiling mid-sentence. **A truncated answer is still an
  HTTP 200.** Nothing raises. If the application does not inspect this field it
  will happily present half an answer as a complete one — a silent correctness
  bug, not a crash.
- **`prompt_eval_count` / `eval_count`** — the only honest measure of what a call
  cost. Locally the unit is latency and context-window budget rather than money;
  the discipline is identical. `eval_count / eval_duration * 1e9` = tokens/sec.

## Why we're using it here

`/api/chat` over `/api/generate` for two reasons, neither of which is "we want
multi-turn conversation" (V1 is strictly single-turn, `Question -> Answer`):

1. **The system/user split is first-class structure.** A role-tagged message can
   be versioned, diffed and regression-tested. A flat prompt string cannot.
2. **It is the shape the industry converged on.** The seam in
   [[V1 - Minimal LLM Application]] step 4 must be satisfiable by a *hosted*
   provider later; every realistic candidate is messages-with-roles. Wrapping
   the older completion-style shape would bake a mismatch into the interface.

Statelessness is also the reason the context window is a **budget**: in
[[V3 - First RAG System]] every retrieved chunk is resent, in full, on every
call. Prompt size is a cost the application controls, which is precisely why
token counting ([[V1 - Minimal LLM Application]] step 8) has to become a habit
*before* RAG lands rather than after.

## Alternatives considered

- **`POST /api/generate`** (Ollama, completion-style: flat `prompt` + separate
  `system` string). Rejected — see above. Fine for a one-off text completion,
  wrong foundation for a seam.
- **The `ollama` Python SDK** instead of raw HTTP. Deliberately deferred for
  step 3: an abstraction is only understandable after seeing the thing it hides.
  Reconsider at step 4, when the question becomes what the wrapper should own.

## Used in

- [[V1 - Minimal LLM Application]] — steps 3, 4, 5, 6, 7, 8.
- [[V3 - First RAG System]] — retrieved chunks are resent as message text.
- [[V8 - Tools and Structured Operations]], [[V9 - Agentic Workflow]] — the
  tool-call loop is the application executing tools and appending results.

## Notes

- Durations are **nanoseconds**, not milliseconds. Easy to be off by 10^6.
- `"stream": false` matters: streaming returns newline-delimited JSON objects,
  not one body. Step 3 should ask for the non-streaming form.
- Recorded 2026-08-30, prompted by the misconception that the response carries
  conversation history, tool executions and retrieved chunks.
