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

export default async function PlansPage() {
  let tiers: Awaited<ReturnType<typeof getTiers>>['tiers'] = [];
  try {
    tiers = (await getTiers()).tiers || [];
  } catch {
    tiers = [];
  }
  return (
    <main>
      <header className="siteHeader"><a className="brand" href="/">Evidrai</a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage">
        <p className="eyebrow">Plans</p>
        <h1>Choose the level of verification you need.</h1>
        <p className="lead">Start with fast claim checks. Upgrade when deeper evidence review, speech/video workflows, saved reports, or research-scale usage matter.</p>
        {tiers.length > 0 ? (
          <div className="planCards">
            {tiers.map((tier) => (
              <article className="planCard" key={tier.tier}>
                <p className="eyebrow">{tier.tier}</p>
                <h2>{tier.label}</h2>
                <p>{tier.description}</p>
                <ul>
                  {Object.entries(tier.features).filter(([, enabled]) => enabled).map(([feature]) => (
                    <li key={feature}>{featureLabels[feature] || feature}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        ) : <p className="muted">Plan details are temporarily unavailable.</p>}
      </section>
    </main>
  );
}
