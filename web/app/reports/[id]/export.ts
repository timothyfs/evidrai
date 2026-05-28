import type { AssessmentResponse } from '../../../lib/api';

function safe(value: unknown) {
  return typeof value === 'string' ? value : value == null ? '' : String(value);
}

function linesToMarkdown(items: string[]) {
  return items.filter(Boolean).map((item) => `- ${item}`).join('\n');
}

export function reportMarkdown(report: AssessmentResponse) {
  const sources = (report.sources || []).map((source, index) => {
    const label = source.title || source.domain || `Source ${index + 1}`;
    const url = source.url ? ` — ${source.url}` : '';
    const summary = source.summary || source.classification_reason || '';
    return `### ${index + 1}. ${label}\n\n${summary}\n\n${source.stance ? `Stance: ${source.stance}\n\n` : ''}${url}`;
  }).join('\n\n');

  const breakdown = (report.claim_breakdown || []).map((item) => `${item.text}: ${item.assessment} (${item.confidence})`).join('\n');

  return `# Evidrai report\n\n` +
    `## Claim\n\n${safe(report.request.claim) || 'Untitled claim'}\n\n` +
    `## Verdict\n\n${safe(report.verdict.label)} · ${safe(report.verdict.confidence)} confidence\n\n` +
    `${safe(report.verdict.summary)}\n\n` +
    `${report.verdict.key_caveat ? `**Key caveat:** ${report.verdict.key_caveat}\n\n` : ''}` +
    `## Metadata\n\n${linesToMarkdown([`Assessment ID: ${report.assessment_id}`, `Created: ${report.created_at}`, `Mode: ${report.mode}`, `Source URL: ${report.request.source_url || ''}`])}\n\n` +
    `${breakdown ? `## Claim breakdown\n\n${breakdown}\n\n` : ''}` +
    `## Evidence sources\n\n${sources || 'No sources recorded.'}\n`;
}

export function downloadText(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
