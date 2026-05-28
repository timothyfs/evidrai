const focusAreas = [
  {
    title: 'Product and evidence workflows',
    text: 'Turning claim checking into a repeatable workflow for people who need evidence trails, not black-box answers.',
  },
  {
    title: 'Verification architecture',
    text: 'Building the API, persistence, scoring, source classification, and report model that make assessments inspectable.',
  },
  {
    title: 'Early-access learning loop',
    text: 'Using tester feedback to harden verdict behaviour, source handling, UI clarity, and researcher/journalist capability.',
  },
];

const operatingPrinciples = [
  'Be honest about limits',
  'Do not confuse admin rights with product tiers',
  'Do not sell future capability as live capability',
  'Prefer inspectable evidence over confident theatre',
];

export default function TeamPage() {
  return (
    <main>
      <header className="siteHeader"><a className="brand logoBrand" href="/" aria-label="Evidrai home"><img src="/brand/evidrai-logo-full.jpg" alt="Evidrai" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage pageHero">
        <p className="eyebrow">Team</p>
        <h1>A small team building evidence-first verification tools.</h1>
        <p className="lead">Evidrai is intentionally early and focused. The work now is to prove the product with selected users, tighten the verification workflow, and build only the capabilities that make evidence easier to inspect.</p>
      </section>

      <section className="marketingGrid threeColumns">
        {focusAreas.map((item) => (
          <article className="infoCard" key={item.title}>
            <h2>{item.title}</h2>
            <p>{item.text}</p>
          </article>
        ))}
      </section>

      <section className="card marketingPage splitSection">
        <div>
          <p className="eyebrow">How we build</p>
          <h1>Controlled early access, not hype-cycle theatre.</h1>
          <p className="lead">The product is being shaped around practical verification use cases: claims, articles, transcripts, reports, source trails, and feedback that can become regression tests.</p>
        </div>
        <div className="principleList">
          {operatingPrinciples.map((item) => <span key={item}>{item}</span>)}
        </div>
      </section>
    </main>
  );
}
