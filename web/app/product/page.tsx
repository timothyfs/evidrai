const workflows = [
  {
    title: 'Claim assessment',
    text: 'Check a specific factual claim, headline, post, or assertion. Evidrai returns a verdict, confidence, caveats, and source trail.',
  },
  {
    title: 'Speech and video review',
    text: 'Extract checkable claims from a transcript or supported video URL, then choose which claims deserve verification.',
  },
  {
    title: 'Saved evidence reports',
    text: 'Assessments are saved to your account so you can revisit evidence, feedback, verdicts, and source scoring later.',
  },
  {
    title: 'Enterprise Gateway Mode',
    text: 'A verification control point for AI-generated outputs in consequential workflows. Each output gets a pass, review, or block decision — evidence-backed, policy-driven, and auditable.',
  },
];

const principles = [
  'Evidence beats repetition',
  'Confidence is not certainty',
  'Primary sources matter',
  'Caveats stay visible',
];

const liveNow = [
  'Standard claim checks with evidence review',
  'Article/source URL context',
  'Pasted transcript speech audits',
  'Best-effort YouTube transcript extraction',
  'Saved reports and feedback capture',
  'Evidence scorecards and source grouping',
  'Polished report export and share links',
  'Enterprise Gateway Mode (early access)',
];

const comingNext = [
  'Researcher evidence ledger',
  'Durable source snapshots',
  'Standard API access with keys and usage limits',
];

export default async function ProductPage() {
  return (
    <main>
      <header className="siteHeader"><a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a><nav className="staticNav"><a href="/product" aria-current="page">Product</a><a href="/enterprise">Enterprise</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage pageHero">
        <p className="eyebrow">Product</p>
        <h1>Evidence checks for claims, speeches, articles, and public narratives.</h1>
        <p className="lead">Evidrai helps early-access users separate evidence from repetition. It is built for people who need to inspect why a claim looks supported, contradicted, weak, or still unresolved.</p>
        <div className="pageActions"><a className="button" href="/">Open Verify</a><a className="button secondary" href="/plans">View early-access plans</a></div>
      </section>

      <section className="marketingGrid twoColumns">
        {workflows.map((item) => (
          <article className="infoCard" key={item.title}>
            <h2>{item.title}</h2>
            <p>{item.text}</p>
          </article>
        ))}
      </section>

      <section className="card marketingPage splitSection">
        <div>
          <p className="eyebrow">How it works</p>
          <h1>Show the work, not just a verdict.</h1>
          <p className="lead">Each assessment is designed to expose the reasoning path: what was checked, which sources mattered, how strong the evidence was, and what uncertainty remains.</p>
        </div>
        <div className="principleList">
          {principles.map((item) => <span key={item}>{item}</span>)}
        </div>
      </section>

      <section className="card marketingPage splitSection enterpriseCallout">
        <div>
          <p className="eyebrow">Evidrai Enterprise</p>
          <h2>A verification layer for AI workflows that carry real consequences.</h2>
          <p>Enterprise Gateway Mode puts Evidrai between your AI system and the actions it would trigger. Every decision is policy-driven, evidence-backed, and written to an audit log. Pass, review, or block — inline, in one API call.</p>
          <div className="pageActions"><a className="button" href="/enterprise">Learn about Enterprise</a></div>
        </div>
        <div className="principleList">
          <span>Pass — evidence supports the output</span>
          <span>Review — route to human verification</span>
          <span>Block — evidence contradicts or is absent</span>
          <span>Full audit record on every decision</span>
        </div>
      </section>

      <section className="marketingGrid twoColumns">
        <article className="infoCard">
          <p className="eyebrow">Available now</p>
          <ul className="cleanList">
            {liveNow.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </article>
        <article className="infoCard subduedCard">
          <p className="eyebrow">Coming next</p>
          <ul className="cleanList">
            {comingNext.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </article>
      </section>
    </main>
  );
}
