# Downstream item export (v1)

`GET /api/sessions/{session_id}/export` returns a read-only JSON snapshot of an
Identifier item. Future pricing and market-research systems should consume this
export rather than call Langflow directly or depend on prompts, providers or local
storage. Identifier remains a standalone identification application; this endpoint
does not perform pricing, comparable-sales research or resale recommendations.

The endpoint uses the existing local API host/origin restrictions and `no-store`
caching policy. It requires no mutation header. It makes no model or Langflow
call, writes no files, and does not change recognition or user-decision behavior.
Invalid or missing session IDs return the existing HTTP 404 response:
`{"detail": "Item session not found"}`.

## Response fields

| Field | v1 representation |
| --- | --- |
| `schema_version` | String `"1"` |
| `session_id` | Application session UUID, never a Langflow session ID |
| `exported_at` | UTC ISO 8601 timestamp generated for this response |
| `ready_for_market_research` | Boolean indicating a current accepted user decision |
| `recognition_status` | Current guarded `Resolved`, `Needs Evidence`, `Unresolved`, or `null` when no result exists |
| `canonical_identity` | Accepted decision's guarded identity object, or `null` |
| `user_decision` | Current decision's `action`, `at` (UTC ISO 8601), and `attempt_number` (integer), or `null` |
| `identifiers` | Sorted, unique array of strings recovered by the existing `identifiers_for(session)` helper; empty array when none are known |
| `recognition_evidence` | Current guarded result's evidence fields, described below |
| `images` | Array of image metadata and local API preview URLs; empty array when there are no images |

Readiness is true only when the current decision, after the existing naming
guard, has action `confirmed`, `corrected`, or `accepted general identity`.
`canonical_identity` contains exactly `name`, `brand`, `product_name`,
`style_accent`, and `item_type`, each a string or `null`. A correction takes
precedence over the model identity. An accepted general identity can be ready
while recognition remains Unresolved and `product_name` remains `null`.

A rejected or undecided result has readiness false and canonical identity null,
even when the model says Resolved. Rejected decision metadata is still included.
The current `decision` slot is authoritative: historical acceptances in `decisions`
are never substituted. Starting a new recognition attempt clears the current
decision through the existing workflow. An old decision invalidated by the naming
guard is treated as absent without rewriting stored data.

Identifiers remain separate from marketed product identity. The helper recovers
codes from recorded manual inputs and labeled recognition evidence; it returns
values, not reliably typed UPC/MPN/SKU objects. Export does not infer code types or
promote codes into `product_name`.

`recognition_evidence` contains exactly `candidate`, `evidence`,
`missing_evidence`, `next_action`, `reason_unresolved`,
`missing_optional_information`, and `sources`. These retain the existing textual
representation; candidates are not canonical identities. With no current result,
`candidate` is null and the remaining fields are empty strings. Idle, processing,
and failed sessions can be exported without inventing recognition results.

Each image contains exactly `id`, `filename` (the stored basename), `width`,
`height`, `submitted`, and `preview_url`. Submitted and pending images are both
included; consumers can distinguish them using `submitted`. For example:

```json
{
  "id": "a7c5d519da314bc69e78d23029ce741f",
  "filename": "label.png",
  "width": 1200,
  "height": 1600,
  "submitted": true,
  "preview_url": "/api/sessions/91869997-f5db-45e7-b56c-33998b774e41/images/a7c5d519da314bc69e78d23029ce741f"
}
```

Resolve preview URLs against the local Identifier API origin. They serve existing
normalized JPEG previews, not original filesystem locations. The projection
excludes raw attempts, prompt inputs, decision history, execution diagnostics,
credentials, Langflow IDs and runtime/storage metadata. Existing session and
recognition endpoints remain unchanged.
