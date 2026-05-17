import { getTiers } from '../../lib/api';

const featureLabels: Record<string, string> = {
  fast_claims: 'Fast claim checks',
  deep_claims: 'Deep claim checks',
  speech_audit: 'Speech/video audit',
  feedback: 'Feedback',
  share_reports: 'Shareable reports',
  exports: 'Exports',
  evidence_ledger: 'Evidence ledger',
  source_snapshots: 'Source snapshots',
  api_access: 'API access',
};

const methodologySteps = [
  {
    title: '1. Normalize the claim',
    text: 'Evidrai separates the checkable factual claim from rhetoric, opinion, framing, and repetition so the assessment is anchored on something specific.',
  },
  {
    title: '2. Gather relevant evidence',
    text: 'The system looks for sources that can corroborate, contradict, contextualize, or weaken the claim. More sources do not automatically mean stronger evidence.',
  },
  {
    title: '3. Classify source role and quality',
    text: 'Sources are grouped by how they relate to the claim, with attention to credibility, proximity to the evidence, transparency, and whether the source is primary, expert, institutional, or secondary.',
  },
  {
    title: '4. Compare evidence, not volume',
    text: 'Evidrai weighs corroboration, contradictions, missing context, and caveats. Repetition across low-quality sources is treated differently from independent supporting evidence.',
  },
  {
    title: '5. Produce an inspectable assessment',
    text: 'The verdict, confidence, caveats, reasoning, and source trail are shown together so users can see why the system reached its assessment and where uncertainty remains.',
  },
];

export default async function PlansPage() {
  let tiers: Awaited<ReturnType<typeof getTiers>>['tiers'] = [];
  try {
    tiers = (await getTiers()).tiers || [];
  } catch {
    tiers = [];
  }
  const featureKeys = tiers[0] ? Object.keys(tiers[0].features) : [];
  return (
    <main>
      <header className="siteHeader"><a className="brand" href="/">Evidrai</a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Evidence</a><a href="/about">About</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage">
        <p className="eyebrow">Evidence methodology</p>
        <h1>Trust is earned by showing the work.</h1>
        <p className="lead">Evidrai does not claim to determine absolute truth. It produces transparent, evidence-based assessments that explain what is supported, what is contested, and where confidence is limited.</p>
        <div className="methodologyGrid">
          {methodologySteps.map((step) => (
            <article className="methodologyCard" key={step.title}>
              <h2>{step.title}</h2>
              <p>{step.text}</p>
            </article>
          ))}
        </div>
        <div className="trustSignals methodologySignals">
          <span>Evidence over repetition</span>
          <span>Confidence is not certainty</span>
          <span>Reasoning remains inspectable</span>
          <span>Caveats are surfaced</span>
        </div>
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">Plans</p>
        <h1>Start free. Upgrade when deeper verification matters.</h1>
        {tiers.length > 0 ? <div className="matrixGrid marketingMatrix">
          <strong>Feature</strong>
          {tiers.map((tier) => <strong key={tier.tier}>{tier.label}</strong>)}
          {featureKeys.map((feature) => [
            <span key={`${feature}-label`}>{featureLabels[feature] || feature}</span>,
            ...tiers.map((tier) => <span key={`${feature}-${tier.tier}`}>{tier.features[feature] ? 'Yes' : 'No'}</span>),
          ])}
        </div> : <p className="muted">Plan details are temporarily unavailable.</p>}
      </section>
    </main>
  );
}
