const contactRoutes = [
  {
    title: 'Early access users',
    text: 'Send rough feedback: what you tested, whether the verdict made sense, what felt confusing, and whether you would use it before trusting or sharing a claim.',
  },
  {
    title: 'Researchers and journalists',
    text: 'Tell us what evidence workflow you need: report export, source trails, transcripts, repeatable research notes, or evidence ledgers.',
  },
  {
    title: 'Partners and advisors',
    text: 'Useful conversations are around verification workflows, trust infrastructure, evidence provenance, and responsible AI product design.',
  },
];

const feedbackPrompts = [
  'What claim, article, or transcript did you test?',
  'Did the verdict match the evidence shown?',
  'Was anything too confident, too cautious, or unclear?',
  'What would stop you using this in a real workflow?',
];

export default function ContactPage() {
  return (
    <main>
      <header className="siteHeader"><a className="brand logoBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-logo-full.jpg" alt="" /><img className="logoDark" src="/brand/evidrai-logo-full-dark.jpg" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage pageHero">
        <p className="eyebrow">Contact</p>
        <h1>Talk to us about evidence, trust, and verification workflows.</h1>
        <p className="lead">Evidrai is in controlled early access. The most useful contact right now is specific feedback from real checks, real transcripts, and real moments where trust was unclear.</p>
        <div className="pageActions"><a className="button" href="/">Test Evidrai</a><a className="button secondary" href="/about">Read the methodology</a></div>
      </section>

      <section className="marketingGrid threeColumns">
        {contactRoutes.map((item) => (
          <article className="infoCard" key={item.title}>
            <h2>{item.title}</h2>
            <p>{item.text}</p>
          </article>
        ))}
      </section>

      <section className="card marketingPage splitSection">
        <div>
          <p className="eyebrow">Feedback format</p>
          <h1>Rough notes are better than polished praise.</h1>
          <p className="lead">If you are testing early access, send the messy version. The goal is to find weak assumptions, confusing UI, missing evidence, and workflows that do not yet hold up.</p>
        </div>
        <ul className="cleanList boxedList">
          {feedbackPrompts.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>
    </main>
  );
}
