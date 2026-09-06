const gatewayCapabilities = [
  {
    title: 'Pass / Review / Block decisions',
    text: 'Every AI output is assessed against your policy and consequence level. The gateway returns a structured decision — pass it, route it for human review, or block it — with a full evidence trail.',
  },
  {
    title: 'Consequence-aware policies',
    text: 'Configure how strictly the gateway responds based on what is at stake. High-consequence workflows get tighter evidence thresholds. Low-consequence flows pass with less friction.',
  },
  {
    title: 'Auditable decision log',
    text: 'Every gateway decision is written to a tamper-evident audit record: which policy fired, which rules triggered, which claims were assessed, and what the evidence showed.',
  },
  {
    title: 'Domain-specific verification',
    text: 'Policies are scoped to domains — finance, legal, comms, operations — so evidence requirements match the subject matter rather than applying a single generic threshold.',
  },
  {
    title: 'Synchronous API',
    text: 'A single POST to /v1/gateway/verify returns a structured decision inline. No queue polling. No async callbacks required for the critical path.',
  },
  {
    title: 'Scope-controlled access',
    text: 'Gateway access is explicitly scoped. Standard API keys do not inherit gateway privileges. Enterprise credentials are provisioned separately.',
  },
];

const useCases = [
  {
    sector: 'Financial services',
    example: 'Block or flag AI-generated investment briefings that contain unverified material claims before they reach clients or compliance review.',
  },
  {
    sector: 'Legal and compliance',
    example: 'Route AI-drafted contract summaries or regulatory filings through evidence review before they enter a human approval queue.',
  },
  {
    sector: 'Enterprise comms',
    example: 'Intercept AI-generated press releases, board communications, or customer briefings and require human sign-off on any unverified claims.',
  },
  {
    sector: 'Research and intelligence',
    example: 'Wrap AI-assisted analyst outputs in a verification layer before distributing to clients or publishing internally.',
  },
];

const decisionFlow = [
  { step: '1', title: 'AI output enters the gateway', text: 'Your system sends the AI-generated content, the proposed action, and the domain context.' },
  { step: '2', title: 'Evidrai verifies the claims', text: 'Evidence is gathered, source quality is scored, and material claims are assessed against the evidence.' },
  { step: '3', title: 'Policy is applied', text: 'The gateway evaluates the assessment against your configured policy and consequence level.' },
  { step: '4', title: 'Decision is returned', text: 'Pass, review, or block — with the triggered rules, evidence summary, and audit record.' },
];

export default function EnterprisePage() {
  return (
    <main>
      <header className="siteHeader">
        <a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home">
          <img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" />
          <img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" />
        </a>
        <nav className="staticNav">
          <a href="/product">Product</a>
          <a href="/enterprise" aria-current="page">Enterprise</a>
          <a href="/plans">Plans</a>
          <a href="/about">About</a>
          <a href="/team">Team</a>
          <a href="/contact">Contact</a>
          <a href="/">Verify</a>
        </nav>
      </header>

      <section className="card marketingPage pageHero">
        <p className="eyebrow">Evidrai Enterprise</p>
        <h1>A verification layer for AI workflows that carry real consequences.</h1>
        <p className="lead">Evidrai Enterprise adds a structured gateway between AI-generated outputs and the actions they trigger. Every decision is policy-driven, evidence-backed, and fully auditable.</p>
        <div className="pageActions">
          <a className="button" href="/contact">Request access</a>
          <a className="button secondary" href="/developers">Developer docs</a>
          <a className="button secondary" href="/product">Explore the product</a>
        </div>
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">Where Evidrai sits</p>
        <h2>A verification layer between AI output and the action it triggers.</h2>
        <figure className="archDiagram">
          <svg className="archSvg" viewBox="0 0 980 340" role="img" aria-labelledby="archTitle archDesc" preserveAspectRatio="xMidYMid meet">
            <title id="archTitle">Evidrai verification architecture</title>
            <desc id="archDesc">An AI system or agent produces output; Evidrai analyses the evidence and returns a structured assessment; your policy or a human decides to pass, review, or block the action.</desc>
            <defs>
              <marker id="archArrowHead" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
                <path d="M0,0 L9,4.5 L0,9 Z" className="archArrowFill" />
              </marker>
            </defs>

            {/* Row 1: input */}
            <rect className="archBox" x="360" y="20" width="260" height="66" rx="14" />
            <text className="archBoxTitle" x="490" y="47" textAnchor="middle">AI / Agent / Application</text>
            <text className="archBoxSub" x="490" y="68" textAnchor="middle">Produces an output or proposes an action</text>
            <line className="archLine" x1="490" y1="86" x2="490" y2="120" markerEnd="url(#archArrowHead)" />

            {/* Row 2: Evidrai engine */}
            <rect className="archBox archAccent" x="150" y="124" width="680" height="120" rx="16" />
            <text className="archEngineLabel" x="180" y="150">EVIDRAI EVIDENCE ENGINE</text>
            <g>
              <rect className="archInner" x="172" y="164" width="150" height="60" rx="10" />
              <text className="archInnerText" x="247" y="190" textAnchor="middle">Claim</text>
              <text className="archInnerText" x="247" y="208" textAnchor="middle">decomposition</text>

              <rect className="archInner" x="338" y="164" width="150" height="60" rx="10" />
              <text className="archInnerText" x="413" y="190" textAnchor="middle">Evidence retrieval</text>
              <text className="archInnerText" x="413" y="208" textAnchor="middle">&amp; source scoring</text>

              <rect className="archInner" x="504" y="164" width="150" height="60" rx="10" />
              <text className="archInnerText" x="579" y="190" textAnchor="middle">Corroboration</text>
              <text className="archInnerText" x="579" y="208" textAnchor="middle">&amp; contradiction</text>

              <rect className="archInner" x="670" y="164" width="140" height="60" rx="10" />
              <text className="archInnerText" x="740" y="190" textAnchor="middle">Confidence</text>
              <text className="archInnerText" x="740" y="208" textAnchor="middle">&amp; caveats</text>
            </g>
            <line className="archLine" x1="490" y1="244" x2="490" y2="278" markerEnd="url(#archArrowHead)" />

            {/* Row 3: assessment */}
            <rect className="archBox" x="300" y="282" width="380" height="40" rx="12" />
            <text className="archBoxTitle" x="490" y="307" textAnchor="middle">Inspectable structured assessment (verdict · sources · reasoning)</text>

            {/* Row 3 -> decisions: fan out */}
            <line className="archLine" x1="360" y1="322" x2="150" y2="322" />
            <line className="archLine" x1="620" y1="322" x2="830" y2="322" />
          </svg>
          <div className="archDecisions" aria-hidden="false">
            <span className="archPill pass">PASS — proceed</span>
            <span className="archPill review">REVIEW — route to human</span>
            <span className="archPill block">BLOCK — stop the action</span>
          </div>
          <figcaption className="muted archNote">Evidrai evaluates the evidence. Your application, policy, or a human decides what to do with that assessment — every decision written to an audit record.</figcaption>
        </figure>
      </section>

      <section className="card marketingPage splitSection">
        <div>
          <p className="eyebrow">The problem</p>
          <h1>AI gets things wrong. Not randomly — plausibly.</h1>
          <p className="lead">Plausible-sounding errors are the hard ones. They pass human review because they look right. They cause real damage when they reach clients, regulators, or public channels.</p>
          <p>Evidrai Enterprise sits between your AI system and the action it would trigger. It checks the evidence, applies your policy, and gives you a structured decision before anything consequential happens.</p>
        </div>
        <div className="principleList">
          <span>Pass — evidence supports the output</span>
          <span>Review — route to human verification</span>
          <span>Block — evidence contradicts or is absent</span>
        </div>
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">How the gateway works</p>
        <h2>From AI output to decision in one call.</h2>
        <div className="trustJourneySteps">
          {decisionFlow.map((item) => (
            <article key={item.step}>
              <span>{item.step}</span>
              <strong>{item.title}</strong>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketingGrid threeColumns">
        {gatewayCapabilities.map((item) => (
          <article className="infoCard" key={item.title}>
            <h2>{item.title}</h2>
            <p>{item.text}</p>
          </article>
        ))}
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">Where it applies</p>
        <h2>Built for workflows where a wrong output has a cost.</h2>
        <div className="marketingGrid twoColumns useCaseGrid">
          {useCases.map((item) => (
            <article className="infoCard" key={item.sector}>
              <p className="eyebrow">{item.sector}</p>
              <p>{item.example}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card marketingPage splitSection">
        <div>
          <p className="eyebrow">API</p>
          <h2>One endpoint. Synchronous. Structured.</h2>
          <p>POST to <code>/v1/gateway/verify</code> with your AI output, proposed action, domain, and consequence level. Get back a decision, triggered rules, and a full evidence summary — inline, in one response.</p>
          <p>Gateway access is provisioned separately from standard API keys. Audit records are written automatically on every call.</p>
          <div className="pageActions"><a className="button secondary" href="/developers">Read the developer docs</a></div>
        </div>
        <div className="principleList">
          <span>gateway:write scope required</span>
          <span>Synchronous response</span>
          <span>Structured JSON decision</span>
          <span>Automatic audit record</span>
        </div>
      </section>

      <section className="card marketingPage centredSection">
        <p className="eyebrow">Early access</p>
        <h2>Evidrai Enterprise is in private early access.</h2>
        <p className="lead">We are working with a small set of organisations in finance, legal, and enterprise AI to prove the gateway in real workflows before a wider rollout.</p>
        <p>If your team is building AI workflows where errors carry compliance, reputational, or financial risk, we want to talk.</p>
        <div className="pageActions">
          <a className="button" href="/contact">Get in touch</a>
          <a className="button secondary" href="/plans">View standard plans</a>
        </div>
      </section>
    </main>
  );
}
