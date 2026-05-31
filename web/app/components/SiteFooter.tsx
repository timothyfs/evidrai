import { legalLinks, trustLinks } from '../../lib/policies';

export default function SiteFooter() {
  return (
    <footer className="siteFooter" aria-label="Evidrai footer">
      <div className="siteFooterBrand">
        <a className="brand logoBrand eyeBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-eye-light.png" alt="" /><img className="logoDark" src="/brand/evidrai-eye-dark.png" alt="" /></a>
        <div>
          <strong>Evidrai</strong>
          <p>Because trust needs evidence.</p>
        </div>
      </div>
      <nav className="siteFooterLinks" aria-label="Legal and trust links">
        <section>
          <h2>Legal</h2>
          {legalLinks.map((link) => <a href={link.href} key={link.href}>{link.label}</a>)}
        </section>
        <section>
          <h2>Trust</h2>
          {trustLinks.map((link) => <a href={link.href} key={link.href}>{link.label}</a>)}
        </section>
      </nav>
    </footer>
  );
}
