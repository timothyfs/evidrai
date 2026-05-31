import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { policies, policyBySlug } from '../../lib/policies';

export function generateStaticParams() {
  return policies.map((policy) => ({ policySlug: policy.slug }));
}

type PageProps = { params: Promise<{ policySlug: string }> };

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { policySlug } = await params;
  const policy = policyBySlug(policySlug);
  if (!policy) return {};
  return { title: `${policy.title} | Evidrai`, description: policy.intro };
}

export default async function PolicyPage({ params }: PageProps) {
  const { policySlug } = await params;
  const policy = policyBySlug(policySlug);
  if (!policy) notFound();

  return (
    <main>
      <header className="siteHeader"><a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <article className="card marketingPage policyPage">
        <p className="eyebrow">{policy.group}</p>
        <h1>{policy.title}</h1>
        <p className="lastUpdated">Last Updated: [DATE]</p>
        <p className="lead">{policy.intro}</p>
        {policy.legalReviewNote && <p className="policyNotice">These documents are provided for transparency and are subject to legal review.</p>}

        {policy.summary && (
          <section className="policySummary" aria-labelledby="plain-english-summary">
            <h2 id="plain-english-summary">Plain English Summary</h2>
            <ul>
              {policy.summary.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </section>
        )}

        <div className="policyContent">
          {policy.sections.map((section) => (
            <section key={section.heading}>
              <h2>{section.heading}</h2>
              {section.paragraphs?.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              {section.bullets && <ul>{section.bullets.map((item) => <li key={item}>{item}</li>)}</ul>}
            </section>
          ))}
        </div>

        {policy.contact && (
          <section className="policyContact">
            <h2>Contact</h2>
            <p>Questions may be directed to <a href={`mailto:${policy.contact}`}>{policy.contact}</a>.</p>
          </section>
        )}
      </article>
    </main>
  );
}
