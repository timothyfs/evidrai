import { getTiers } from '../../lib/api';

const featureLabels: Record<string, string> = {
  fast_claims: 'Fast claim checks',
  deep_claims: 'Deep claim checks',
  speech_audit: 'Speech/video audit',
  feedback: 'Feedback loop',
  simple_share_reports: 'Simple branded shares',
  share_reports: 'Full evidence report shares',
  exports: 'Exports',
  evidence_ledger: 'Evidence ledger',
  source_snapshots: 'Source snapshots',
  api_access: 'API access',
};

const availableNow = new Set([
  'fast_claims',
  'deep_claims',
  'speech_audit',
  'feedback',
  'simple_share_reports',
  'share_reports',
  'exports',
]);

const comingSoon = new Set([
  'evidence_ledger',
  'source_snapshots',
  'api_access',
]);

function featureState(feature: string) {
  if (availableNow.has(feature)) return 'available';
  if (comingSoon.has(feature)) return 'soon';
  return 'available';
}

function tierNote(tier: string) {
  if (tier === 'free') return 'Good for lightweight early-access testing, occasional checks, and simple branded sharing.';
  if (tier === 'pro') return 'Deep checks, speech/video workflows, public report shares, and exports are available now.';
  if (tier === 'researcher') return 'Preview tier for heavier research workflows. Higher limits and exports are active; ledger, snapshots, and API access are being built out.';
  return '';
}

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
        <p className="lead">Evidrai is in controlled early access. Core verification, saved reports, feedback, and speech/video workflows are live; advanced research workflows are being added carefully rather than over-promised.</p>
        <div className="earlyAccessNotice">
          <strong>Early access promise</strong>
          <span>Every plan below separates what works now from what is coming next. No fake enterprise bingo. Refreshing, frankly.</span>
        </div>
        {tiers.length > 0 ? (
          <div className="planCards">
            {tiers.map((tier) => {
              const enabledFeatures = Object.entries(tier.features).filter(([, enabled]) => enabled);
              const nowFeatures = enabledFeatures.filter(([feature]) => featureState(feature) === 'available');
              const soonFeatures = enabledFeatures.filter(([feature]) => featureState(feature) === 'soon');
              return (
                <article className="planCard" key={tier.tier}>
                  <p className="eyebrow">{tier.tier === 'researcher' ? 'researcher preview' : tier.tier}</p>
                  <h2>{tier.label}</h2>
                  <p>{tier.description}</p>
                  {tierNote(tier.tier) && <p className="planNote">{tierNote(tier.tier)}</p>}
                  <div className="featureGroup">
                    <strong>Available now</strong>
                    <ul>
                      {nowFeatures.map(([feature]) => (
                        <li key={feature}>{featureLabels[feature] || feature}</li>
                      ))}
                    </ul>
                  </div>
                  {soonFeatures.length > 0 && (
                    <div className="featureGroup comingSoonGroup">
                      <strong>Coming next</strong>
                      <ul>
                        {soonFeatures.map(([feature]) => (
                          <li key={feature}><span>{featureLabels[feature] || feature}</span><em>Coming soon</em></li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <p className="planLimits">Saved reports: {tier.limits.saved_reports} · Speech claims/audit: {tier.limits.max_speech_claims}</p>
                </article>
              );
            })}
          </div>
        ) : <p className="muted">Plan details are temporarily unavailable.</p>}
      </section>
    </main>
  );
}
