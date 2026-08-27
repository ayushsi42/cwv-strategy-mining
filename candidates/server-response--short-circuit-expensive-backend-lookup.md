---
issue_type: server-response--short-circuit-expensive-backend-lookup
parent_strategy: server-response
risk_tier: low
cwv_metrics:
  - server latency
  - TTFB
  - FCP
source_prs:
  - DEFRA/ffc-ahwr-backoffice#340
  - internxt/payments-server#296
  - knocklabs/css_inline#11
required_validation:
  - nesting_depth_guard_enabled
  - pathological_input_rejected_before_expensive_work
forbidden_techniques: []
---

# Short-circuit expensive backend lookup

> **Risk tier:** low · **Parent strategy:** server-response · **CWV metrics:** server latency, TTFB, FCP

## What this addresses

This strategy reduces origin-side work on the response path by checking a cheap rejection or bypass condition before invoking an expensive backend lookup, parser pass, or upstream call.

The supplied evidence shows three variants of the same mechanism:

- **Input complexity guard before parsing/inlining** in `knocklabs/css_inline#11`
  - A fast byte scan checks HTML nesting depth before running the inlining parser.
  - Deeply nested input returns `{:error, :nesting_depth_exceeded}` instead of proceeding.
- **Conditional subscription lookup in request handling** in `internxt/payments-server#296`
  - The handler first derives feature applicability from local services.
  - It only calls `paymentService.getActiveSubscriptions(customerId)` when backups are still disabled after the cheaper check.
  - If there is no active subscription and the user is not lifetime, it returns an immediate success response with both features disabled.
- **Conditional endpoint/tool registration or execution** in `DEFRA/ffc-ahwr-backoffice#340`
  - Several server-side operations were replaced with immediate OK responses.
  - The regression evidence frames the general pattern: skipping registration or execution of unused tools reduces server-side work and can avoid sending or parsing extra response content for requests that do not need those features.

This is a server-response optimization because the work is avoided before the expensive part of response generation, which can lower server latency and therefore affect TTFB and downstream FCP.

## When to apply / when to skip

### Apply

Use this strategy when all of the following are true:

- A request path performs an expensive backend lookup, parser pass, or upstream call that is only needed for some inputs.
- There is a cheap, deterministic precondition that can safely decide whether the expensive work is unnecessary.
- The response can be returned immediately with a valid success or error outcome when the guard fails.
- The guard can be validated from request-local data or a fast scan without first doing the expensive work.

### Skip

Do not apply this strategy when any of the following are true:

- The expensive work is required for every valid request.
- The precondition itself requires the same expensive backend call you are trying to avoid.
- The guard would be speculative or approximate in a way that could change correctness.
- You cannot prove from evidence that the bypass is safe for the affected inputs.

## Required validation

### `nesting_depth_guard_enabled`

Observed in `knocklabs/css_inline#11`.

What this validation checks:
- The implementation exposes a guard option that can be enabled or disabled.
- The guard has a configurable limit.
- The default path uses the guard before inlining.
- The code returns a specific error when the limit is exceeded.

Evidence-derived details:
- `check_depth` defaults to `true`.
- `max_depth` defaults to `128`.
- `inline_css` checks `opts.check_depth && exceeds_nesting_depth(...)` before constructing the inliner.
- Exceeding the limit returns `{:error, :nesting_depth_exceeded}`.
- Tests assert rejection for deeply nested HTML and acceptance near but under the limit.

### `pathological_input_rejected_before_expensive_work`

Observed in `knocklabs/css_inline#11` and supported by the regression framing in `storyboardjs/mcp#48`.

What this validation checks:
- The guard runs before the expensive parser or backend work.
- The rejection happens on the request path without invoking the expensive operation.
- The bypass is tied to pathological or unused input, not normal valid traffic.

Evidence-derived details:
- `exceeds_nesting_depth` scans bytes and returns early when the limit is hit.
- The parser/inliner is only constructed after the guard passes.
- The regression evidence explicitly describes skipping unused work to reduce server-side work.

## Good examples

These examples are evidence-derived from the supplied patches.

### Good: guard before expensive parsing/inlining

```elixir
def inline_css(html, opts) do
  max_depth = if opts.max_depth > 0, do: opts.max_depth, else: 128

  if opts.check_depth && exceeds_nesting_depth(html, max_depth) do
    {:error, :nesting_depth_exceeded}
  else
    CSSInliner.options()
    |> CSSInliner.inline(html)
  end
end
```

Why this is good:
- The guard is evaluated first.
- The expensive inliner is only created after the guard passes.
- The error is explicit and deterministic.

### Good: cheap derivation before conditional backend lookup

```ts
const mergedFeatures = await productsService.getApplicableTierForUser({
  userUuid,
  ownersId,
});

let backupsEnabled = mergedFeatures.featuresPerService.backups.enabled;

if (!backupsEnabled) {
  const userSubscriptions = await paymentService.getActiveSubscriptions(customerId);

  if (userSubscriptions.length === 0 && !isLifetimeUser) {
    return res.status(200).send({
      featuresPerService: { antivirus: false, backups: false },
    });
  }

  backupsEnabled = true;
}
```

Why this is good:
- A cheaper local/service-derived result is computed first.
- The expensive subscription lookup runs only when the cheaper result is insufficient.
- The handler returns immediately when the lookup confirms the feature is unavailable.

## Bad examples

These are not taken from the evidence as concrete failing snippets; they are the inverse of the evidence-backed pattern.

### Bad: expensive work before the guard

```elixir
# Anti-pattern: parse/inlining happens before the depth check.
CSSInliner.options()
|> CSSInliner.inline(html)

if exceeds_nesting_depth(html, max_depth) do
  {:error, :nesting_depth_exceeded}
end
```

Why this is bad:
- The expensive work already happened.
- The guard can no longer short-circuit the response path.

### Bad: unconditional backend lookup on every request

```ts
// Anti-pattern: always call the expensive lookup first.
const userSubscriptions = await paymentService.getActiveSubscriptions(customerId);
```

Why this is bad:
- The request always pays the backend cost.
- There is no short-circuit for requests that can be resolved earlier.

## How to verify

Verification should be measurable and tied to the evidence.

### For `nesting_depth_guard_enabled`

Confirm all of the following:

1. The guard option is enabled by default.
2. The limit is configurable.
3. Deeply nested input returns `{:error, :nesting_depth_exceeded}`.
4. Near-limit input still succeeds.

Measurable checks:
- Run the provided regression tests.
- Add or inspect a test that uses deeply nested HTML and expects the error.
- Add or inspect a test that uses near-limit HTML and expects success.

### For `pathological_input_rejected_before_expensive_work`

Confirm all of the following:

1. The guard executes before the expensive parser or backend call.
2. The expensive operation is not invoked when the guard fails.
3. The response is returned immediately on the guarded path.

Measurable checks:
- Instrument or mock the expensive call and assert it is not reached for rejected input.
- Confirm the guard returns before constructing or invoking the expensive component.
- Compare request traces or logs to verify the bypass path avoids the expensive step.

### CWV-oriented observation

Use the supplied metrics only:

- **server latency**: observe whether the guarded path avoids the expensive backend work.
- **TTFB**: observe whether the response path becomes faster when the bypass is taken.
- **FCP**: treat as a downstream effect when the response path contributes to earlier content delivery.

Do not claim a fixed improvement. The evidence provides directional support, not a quantified delta.

## Evidence and confidence

### Observed facts

- `knocklabs/css_inline#11` adds `check_depth` and `max_depth`, performs a fast byte scan, and rejects deeply nested HTML before inlining.
- `internxt/payments-server#296` moves from a direct tier lookup to a cheaper feature derivation plus a conditional subscription lookup, with an immediate success response when no active subscription exists and the user is not lifetime.
- `DEFRA/ffc-ahwr-backoffice#340` replaces several backend calls with immediate OK responses and removes scheduler registration from the server startup path.
- The regression evidence from `storyboardjs/mcp#48` states that conditional endpoint/tool registration reduces server-side work and can avoid sending or parsing extra response content for requests that do not need those features.

### Inference

- These changes implement the same core strategy: short-circuit expensive backend work when a cheaper precondition can safely decide the outcome.
- The likely CWV impact is on server latency and TTFB, with possible downstream FCP benefit when the response path is on the critical path.

### Confidence

Medium. The mechanism is consistent across three repositories, but the supplied measurements are not numeric and the evidence does not include a quantified before/after delta.

## Risks and limitations

- A guard must be correctness-preserving; if it rejects valid inputs, it becomes a functional bug rather than an optimization.
- Fast scans and heuristics can overcount or undercount structural properties; the evidence explicitly notes that the nesting scanner overcounts because void elements are not closed.
- Returning an immediate success response is only safe when the skipped work is truly nonessential for that request context.
- If the expensive lookup is needed to determine authorization, billing state, or user-visible correctness, do not short-circuit unless the evidence shows a safe equivalent result.
- The strategy is most appropriate when the bypass condition is cheap, deterministic, and validated by tests on both sides of the threshold.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **3 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: server-response--short-circuit-expensive-backend-lookup`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
