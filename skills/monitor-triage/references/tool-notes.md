# Datadog MCP traps

Read before running queries. Each of these has already cost a wrong conclusion.

## Query and search

- `search_datadog_events` with `monitor_id:<id>` returns nothing — not a searchable field. Search the monitor's **title string** instead.
- `get_datadog_metric` in scalar mode silently returns NO_DATA for sparse `.as_count()` series that a timeseries request returns points for. Use timeseries with `raw_data: true`.
- `datadog/monitors` is not a real MCP skill name. Use `datadog/incidents-and-alerting`, `datadog/logs`, `datadog/metrics`, `datadog/traces`.

## What the API won't tell you

- The monitors API omits `renotify_interval`, `notify_no_data`, `no_data_timeframe`, and `priority`. Terraform is the source for the first three; the `[P<n>]` prefix in alert event titles gives priority.
- A monitor's `service:` tag may be an AWS integration name with no APM data behind it. That is not a sign the service is broken.

## Series semantics

- A tag value that stops appearing **drops out of the series entirely** rather than reporting 0, so no threshold can fire on it. Only `no_data_timeframe` detects a total stop.
- Multi-alert no-data monitors track only groups they have already observed. A group created and never fired produces no series and stays invisible — not closable with the same metric.
- Counters (`failed_invocations`, `invocations_sent_to_dlq`, `lambda.errors`) don't publish zeros. Their silence is the healthy steady state *and* the misconfigured state. Prefer gauges (queue depth, oldest-message age) when you need negative evidence.
- `aws.events.dead_letter_invocations` does not exist. Querying a nonexistent metric returns "no data," indistinguishable from a real zero — verify metric names before trusting silence.

## Naming

- Near-duplicate service names are common: `foo-mgr` vs `foo-manager`, plus `peer.service:`-prefixed variants. Several may carry real traffic. Say which you chose and why.
- A monitor's Datadog name and the heading in its alert message body are often different strings — the body heading is authored separately in the monitor's message template. Searching Datadog for the heading you read in Slack will find nothing. Get the name from the monitor definition by ID.
