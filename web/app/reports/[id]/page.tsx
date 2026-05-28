import ReportViewer from './ReportViewer';

type ReportPageProps = { params: Promise<{ id: string }> };

export default async function ReportPage({ params }: ReportPageProps) {
  const { id } = await params;
  return (
    <main>
      <header className="siteHeader printHidden"><a className="brand logoBrand" href="/" aria-label="Evidrai home"><img className="logoLight" src="/brand/evidrai-logo-full.jpg" alt="" /><img className="logoDark" src="/brand/evidrai-logo-full-dark.jpg" alt="" /></a><nav className="staticNav"><a href="/product">Product</a><a href="/plans">Plans</a><a href="/about">About</a><a href="/">Verify</a></nav></header>
      <ReportViewer reportId={id} />
    </main>
  );
}
