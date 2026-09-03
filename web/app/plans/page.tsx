import { getTiers } from '../../lib/api';

const featureLabels: Record<string, string> = {
  fast_claims: 'Standard claim checks',
  deep_claims: 'Evidence review',
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

const hiddenCompatibilityFeatures = new Set([
  'fast_claims',
]);

function featureState(feature: string) {
  if (availableNow.has(feature)) return 'available';
  if (comingSoon.has(feature)) return 'soon';
  return 'available';
}

function tierNote(tier: string) {
  if (tier === 'free') return 'Good for occasional checks and simple branded sharing. Same core claim-check quality, lower limits.';
  if (tier === 'pro') return 'More checks, speech/video workflows, public report shares, and exports are available now.';
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
      <header className="siteHeader"><a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/enterprise">Enterprise</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage">
        <p className="eyebrow">Plans</p>
        <h1>Choose the workflow capacity you need.</h1>
        <p className="lead">Every plan uses the same core claim-check quality. Plans differ by volume, saved history, sharing, exports, and research workflows.</p>
        <div className="earlyAccessNotice">
          <strong>Early access promise</strong>
          <span>Every plan below separates what works now from what is coming next. No fake enterprise bingo. Refreshing, frankly.</span>
        </div>
        {tiers.length > 0 ? (
          <div className="planCards">
            {tiers.map((tier) => {
              const enabledFeatures = Object.entries(tier.features).filter(([feature, enabled]) => enabled && !hiddenCompatibilityFeatures.has(feature));
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
                  <p className="planLimits">Saved reports: {tier.limits.saved_reports} · Monthly claim checks: {tier.limits.monthly_deep_checks || tier.limits.monthly_fast_checks} · Speech claims/audit: {tier.limits.max_speech_claims}</p>
                </article>
              );
            })}
          </div>
        ) : <p className="muted">Plan details are temporarily unavailable.</p>}
      </section>

      <section className="card marketingPage enterpriseCallout">
        <div className="enterprisePlanRow">
          <div>
            <p className="eyebrow">Evidrai Enterprise</p>
            <h2>For organisations using AI in consequential workflows.</h2>
            <p>Enterprise adds Gateway Mode: a verification control point that sits between your AI system and the actions it triggers. Every AI output gets a pass, review, or block decision — backed by evidence, governed by your policy, and written to a tamper-evident audit log.</p>
            <p>Includes <code>gateway:write</code> API scope, domain-specific policies, consequence-level controls, and dedicated onboarding.</p>
          </div>
          <div className="enterprisePlanCTA">
            <p className="eyebrow">Private early access</p>
            <p>We are working with a small set of organisations in finance, legal, and enterprise AI. If this fits your workflow, reach out.</p>
            <a className="button" href="/enterprise">Learn more</a>
            <a className="button secondary" href="/contact">Get in touch</a>
          </div>
        </div>
      </section>
    </main>
  );
}
