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
  const featureKeys = tiers[0] ? Object.keys(tiers[0].features) : [];
  return (
    <main>
      <header className="siteHeader"><a className="brand" href="/">Evidrai</a><nav className="staticNav"><a href="/product">Product</a><a href="/about">About</a><a href="/contact">Contact</a><a href="/">App</a></nav></header>
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
