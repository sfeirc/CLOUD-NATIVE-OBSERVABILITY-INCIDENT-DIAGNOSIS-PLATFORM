# Checkout incident runbook

1. Open the diagnosis console on port 8082 and confirm the firing SLO, sample
   count, burn rates, and top hypothesis.
2. Follow cited trace IDs in Grafana Tempo. Verify the parent chain from checkout
   through order and payment, then inspect database/client spans.
3. From the trace view, open correlated Loki logs. Match request ID, trace ID,
   service version, and error attributes.
4. Compare the incident start with deployment annotations. A temporal match is
   evidence, not proof; compare unaffected instances or the prior version.
5. Check CPU, memory, queue depth, and database latency before selecting a
   mitigation. Stop any active chaos experiment on port 8081.
6. Mitigate with the smallest reversible action: stop the experiment, roll back
   the implicated version, disable the feature, or restore the dependency.
7. Confirm both burn windows fall, new traces return to baseline, and the error
   budget stops decreasing before resolving the incident.

For real payment systems, do not retry ambiguous writes until idempotency status
is known. This demonstration uses generated payment IDs and is not a financial
transaction reference architecture.

