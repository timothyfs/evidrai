const endpoints = [
  {
    method: 'POST',
    path: '/v1/gateway/verify',
    text: 'Verify AI-generated output against evidence and your policy. Returns a pass / review / block decision with the triggered rules and full evidence trail. Requires an API key with the gateway:write scope.',
  },
  {
    method: 'POST',
    path: '/assessments/deep',
    text: 'Retrieval-backed evidence assessment of a single claim. Returns the verdict, confidence, source scoring, contradiction handling, caveats, and inspectable reasoning.',
  },
  {
    method: 'POST',
    path: '/assessments/fast',
    text: 'Lower-latency single-pass assessment for lightweight checks.',
  },
  {
    method: 'GET',
    path: '/reports/{id}',
    text: 'Retrieve a previously produced assessment by its persistent verification ID.',
  },
];

const responseFields = [
  'assessment_id — persistent verification ID',
  'verdict — label, confidence, confidence_score, key_caveat, evidence_strength_score',
  'claim_breakdown — decomposed subclaims with supporting / contradicting source IDs',
  'sources — provenance, source type, and per-source scoring factors',
  'evidence_map — sources grouped by role (supports, contradicts, context)',
  'reasoning — inspectable rationale, rule engine, amplification warnings',
  'telemetry — model, tokens, search calls, elapsed_ms, estimated_cost_usd',
];

const gatewayExample = `curl -sS https://api.evidrai.com/v1/gateway/verify \\
  -H 'Content-Type: application/json' \\
  -H 'X-Evidrai-Api-Key: evd_live_...' \\
  -d '{
    "workflow_id": "investment-briefing-prod",
    "request_id": "req-123",
    "ai_output": "The claim your AI system produced.",
    "proposed_action": { "type": "publish_briefing", "description": "Publish briefing" },
    "domain": "finance",
    "consequence_level": "high",
    "policy_id": "finance_default_v1",
    "cited_sources": []
  }'`;

const gatewayResponse = `{
  "schema_version": "gateway_decision.v1",
  "gateway_id": "gw_...",
  "decision": "review",
  "decision_reason": "High-consequence output has a material claim that is only partly supported.",
  "recommended_next_step": "route_to_human_review",
  "policy_id": "finance_default_v1",
  "assessment_id": "uuid",
  "triggered_rules": [ { "rule_id": "material_claim_unverified", "severity": "review" } ],
  "blocking_claims": [],
  "review_claims": ["sc_1"]
}`;

export default function DevelopersPage() {
  return (
    <main>
      <header className="siteHeader"><a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/enterprise">Enterprise</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>

      <section className="card marketingPage pageHero">
        <p className="eyebrow">Developers</p>
        <h1>Evidrai runs programmatically between your AI system and the action it triggers.</h1>
        <p className="lead">The same evidence engine behind Verify is available as a REST API. Send a claim or an AI-generated output; get back a structured, inspectable, machine-readable assessment — or a pass / review / block decision through Gateway Mode.</p>
        <div className="pageActions"><a className="button" href="/enterprise">Evidrai Enterprise</a><a className="button secondary" href="/contact">Request API access</a></div>
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">Authentication</p>
        <h2>API keys with explicit scopes.</h2>
        <p>Authenticate with an API key in the <code>X-Evidrai-Api-Key</code> header. Keys carry explicit scopes — <code>assessments:write</code>, <code>reports:read</code>, and <code>gateway:write</code> — so access is granted deliberately. Gateway Mode requires a key that carries <code>gateway:write</code>; session and anonymous callers are rejected.</p>
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">Endpoints</p>
        <h2>Core verification surface.</h2>
        <div className="apiEndpointList">
          {endpoints.map((endpoint) => (
            <article className="apiEndpoint" key={endpoint.path}>
              <div className="apiEndpointHead"><span className={`apiMethod ${endpoint.method.toLowerCase()}`}>{endpoint.method}</span><code>{endpoint.path}</code></div>
              <p>{endpoint.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card marketingPage splitSection">
        <div>
          <p className="eyebrow">Gateway request</p>
          <h2>One synchronous call.</h2>
          <p>Send the AI output, the proposed downstream action, the domain, and a consequence level. Supply your own <code>cited_sources</code> and they are folded into the evidence set, scored by the same engine as the open web.</p>
          <pre className="codeBlock"><code>{gatewayExample}</code></pre>
        </div>
        <div>
          <p className="eyebrow">Gateway response</p>
          <h2>A structured decision.</h2>
          <pre className="codeBlock"><code>{gatewayResponse}</code></pre>
        </div>
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">Assessment response</p>
        <h2>Machine-readable and inspectable.</h2>
        <p className="lead">Every assessment is a typed JSON contract (<code>schema_version: assessment_response.v1</code>) with a persistent ID, so results are auditable and re-retrievable.</p>
        <ul className="cleanList">
          {responseFields.map((field) => <li key={field}>{field}</li>)}
        </ul>
      </section>

      <section className="card marketingPage centredSection">
        <p className="eyebrow">Access</p>
        <h2>API access is provisioned for Enterprise pilots.</h2>
        <p className="lead">Programmatic and Gateway access are granted per engagement. Tell us about your workflow and we will set up a scoped key.</p>
        <div className="pageActions"><a className="button" href="/contact">Request API access</a><a className="button secondary" href="/enterprise">Learn about Enterprise</a></div>
      </section>
    </main>
  );
}
