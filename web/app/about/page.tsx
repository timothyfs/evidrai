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

export default function AboutPage() {
  return (
    <main>
      <header className="siteHeader"><a className="brand" href="/">Evidrai</a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage">
        <p className="eyebrow">About Evidrai</p>
        <h1>Built to make evidence easier to inspect.</h1>
        <p className="lead">Evidrai is focused on practical verification workflows for people who need to understand whether a claim is supported, contradicted, missing context, or still unproven.</p>
      </section>
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
    </main>
  );
}
