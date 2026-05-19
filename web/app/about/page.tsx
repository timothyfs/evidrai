const methodologySteps = [
  {
    title: '1. Normalise the claim',
    text: 'Evidrai separates the checkable factual claim from rhetoric, opinion, framing, and repetition so the assessment is anchored on something specific.',
  },
  {
    title: '2. Gather relevant evidence',
    text: 'The system looks for sources that can corroborate, contradict, contextualise, or weaken the claim. More sources do not automatically mean stronger evidence.',
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

const scoringFactors = [
  {
    name: 'Authority',
    weight: '30%',
    text: 'Is this source authoritative for this claim type? Primary records, official datasets, filings, transcripts, and direct evidence carry more weight than commentary.',
  },
  {
    name: 'Relevance',
    weight: '25%',
    text: 'Does the source directly address the exact claim, or is it only loosely related background?',
  },
  {
    name: 'Directness',
    weight: '20%',
    text: 'Is the source close to the underlying evidence, or is it repeating what another source claimed?',
  },
  {
    name: 'Recency',
    weight: '10%',
    text: 'Is the source temporally appropriate? Current claims need current evidence; historical claims may need contemporaneous records.',
  },
  {
    name: 'Independence',
    weight: '10%',
    text: 'Does this source add an independent evidence chain, or is it amplifying the same report, briefing, post, or wire story?',
  },
  {
    name: 'Bias risk',
    weight: '5%',
    text: 'Does the source have a direct incentive to frame the claim selectively? Bias risk is treated as a modifier, not a veto.',
  },
];

const scoreBands = [
  ['4.5-5.0', 'Very strong source'],
  ['3.75-4.49', 'Strong source'],
  ['2.75-3.74', 'Useful or mixed source'],
  ['1.75-2.74', 'Weak source'],
  ['0-1.74', 'Poor, indirect, or irrelevant source'],
];

const limitations = [
  'Evidrai is decision support, not an oracle.',
  'YouTube URL extraction is best-effort; pasted transcripts are the reliable fallback.',
  'Evidence can be incomplete when sources are unavailable, blocked, paywalled, or newly developing.',
  'Confidence reflects the reviewed evidence, not absolute certainty.',
];

export default function AboutPage() {
  return (
    <main>
      <header className="siteHeader"><a className="brand" href="/">Evidrai</a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage pageHero">
        <p className="eyebrow">About Evidrai</p>
        <h1>Built to make evidence easier to inspect.</h1>
        <p className="lead">Evidrai is an early-access verification platform for people who need to understand whether a claim is supported, contradicted, missing context, or still unproven.</p>
        <div className="pageActions"><a className="button" href="/">Try Verify</a><a className="button secondary" href="/product">Explore product</a></div>
      </section>

      <section className="card marketingPage splitSection">
        <div>
          <p className="eyebrow">What Evidrai is</p>
          <h1>Evidence assessment, not fact-checking theatre.</h1>
          <p className="lead">The aim is not to produce a magic truth label. The aim is to expose the evidence trail clearly enough that a human can decide what to trust, what to question, and what needs more work.</p>
        </div>
        <ul className="cleanList boxedList">
          {limitations.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

      <section className="card marketingPage">
        <p className="eyebrow">Evidence methodology</p>
        <h1>Trust is earned by showing the work.</h1>
        <p className="lead">Evidrai produces transparent, evidence-based assessments that explain what is supported, what is contested, and where confidence is limited.</p>
        <div className="methodologyGrid">
          {methodologySteps.map((step) => (
            <article className="methodologyCard" key={step.title}>
              <h2>{step.title}</h2>
              <p>{step.text}</p>
            </article>
          ))}
        </div>

        <details className="methodologyScoringDetails" open>
          <summary><span>How Evidrai scoring works</span><small>Source score, evidence strength, confidence</small></summary>
          <div className="scoringMethodIntro">
            <div>
              <strong>Source score</strong>
              <span>0.0-5.0</span>
              <p>How strong an individual source is for the specific claim.</p>
            </div>
            <div>
              <strong>Evidence strength</strong>
              <span>0-10</span>
              <p>How strong the reviewed evidence set is after support, contradiction, and repetition are considered. For false or contradicted claims, this is shown as contradiction strength.</p>
            </div>
            <div>
              <strong>Confidence</strong>
              <span>0-100 signal</span>
              <p>How confident the system should be in the verdict, given source quality and uncertainty.</p>
            </div>
          </div>

          <div className="methodologyScoreGrid">
            {scoringFactors.map((factor) => (
              <article className="methodologyScoreCard" key={factor.name}>
                <div>
                  <strong>{factor.name}</strong>
                  <span>{factor.weight}</span>
                </div>
                <p>{factor.text}</p>
              </article>
            ))}
          </div>

          <div className="scoringBands">
            <h2>Source score bands</h2>
            <div>
              {scoreBands.map(([range, label]) => (
                <span key={range}><strong>{range}</strong>{label}</span>
              ))}
            </div>
          </div>

          <div className="methodologyGuardrails">
            <h2>Guard rails</h2>
            <ul>
              <li>Primary evidence carries more weight than repetition.</li>
              <li>Five articles based on the same briefing may count as one evidence chain.</li>
              <li>Context helps explanation, but should not inflate confidence.</li>
              <li>Strong contradictions reduce confidence in the claim, even when it is widely repeated.</li>
              <li>When a claim is rejected, Evidrai should say “claim unsupported; credible contradiction found” rather than implying the disproof itself is weak.</li>
              <li>No score is shown without an explanation path.</li>
            </ul>
          </div>
        </details>

        <div className="trustSignals methodologySignals">
          <span>Evidence over repetition</span>
          <span>Confidence is not certainty</span>
          <span>Reasoning remains inspectable</span>
          <span>Caveats are surfaced</span>
        </div>
      </section>
    </main>
  );
}
