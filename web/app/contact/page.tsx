'use client';

import { FormEvent, useState } from 'react';
import { submitContactMessage } from '../../lib/api';

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

type ContactTopic = 'general' | 'early_access' | 'research' | 'partnership' | 'support' | 'press' | 'other';

export default function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [organisation, setOrganisation] = useState('');
  const [topic, setTopic] = useState<ContactTopic>('early_access');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setStatus('');
    try {
      const response = await submitContactMessage({
        name,
        email,
        organisation,
        topic,
        message,
        page_url: typeof window === 'undefined' ? '' : window.location.href,
      });
      setStatus(response.message || 'Thanks. Your message has been sent.');
      setName('');
      setEmail('');
      setOrganisation('');
      setTopic('early_access');
      setMessage('');
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not send your message.');
    } finally {
      setBusy(false);
    }
  }

  const isError = status.toLowerCase().includes('could not') || status.toLowerCase().includes('valid') || status.toLowerCase().includes('required');

  return (
    <main>
      <header className="siteHeader"><a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/team">Team</a><a href="/contact">Contact</a><a href="/">Verify</a></nav></header>
      <section className="card marketingPage pageHero">
        <p className="eyebrow">Contact</p>
        <h1>Talk to us about evidence, trust, and verification workflows.</h1>
        <p className="lead">Evidrai is in controlled early access. The most useful contact right now is specific feedback from real checks, real transcripts, and real moments where trust was unclear.</p>
        <div className="pageActions"><a className="button" href="/">Test Evidrai</a><a className="button secondary" href="/about">Read the methodology</a></div>
      </section>

      <section className="card marketingPage contactFormSection">
        <div>
          <p className="eyebrow">Send a message</p>
          <h1>Tell us what you need Evidrai to solve.</h1>
          <p className="lead">Use this for early access, researcher workflows, partnership ideas, press, or support. Submissions go into the admin support queue.</p>
        </div>
        <form className="contactForm" onSubmit={sendMessage}>
          <div className="formRow">
            <label>Name<input required value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" /></label>
            <label>Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label>
          </div>
          <div className="formRow">
            <label>Organisation<input value={organisation} onChange={(event) => setOrganisation(event.target.value)} placeholder="Optional" /></label>
            <label>Topic<select value={topic} onChange={(event) => setTopic(event.target.value as ContactTopic)}>
              <option value="early_access">Early access</option>
              <option value="research">Research / journalism</option>
              <option value="partnership">Partnership</option>
              <option value="support">Support</option>
              <option value="press">Press</option>
              <option value="general">General</option>
              <option value="other">Other</option>
            </select></label>
          </div>
          <label>Message<textarea required minLength={10} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="What are you testing, building, or trying to verify?" /></label>
          <button disabled={busy} type="submit">{busy ? 'Sending…' : 'Send message'}</button>
          {status && <p className={isError ? 'error' : 'muted'}>{status}</p>}
        </form>
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
