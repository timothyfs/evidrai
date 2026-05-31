import type { AssessmentResponse, AssessmentSource } from './api';

function safe(value: unknown) {
  return typeof value === 'string' ? value : value == null ? '' : String(value);
}

function normaliseWhitespace(value: string) {
  return value.replace(/\s+/g, ' ').trim();
}

function markdownEscape(value: string) {
  return safe(value).replace(/\|/g, '\\|').trim();
}

function linesToMarkdown(items: string[]) {
  return items.filter(Boolean).map((item) => `- ${item}`).join('\n');
}

function score(value?: number | null, max = 5) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '';
  return `${Math.abs(value).toFixed(1)}/${max}`;
}

function sourceLabel(source: AssessmentSource, index: number) {
  return source.title || source.domain || `Source ${index + 1}`;
}

function sourceScoreFactors(source: AssessmentSource) {
  const factors = source.scoring_factors || {};
  const labels: Record<string, string> = {
    authority: 'Authority',
    relevance: 'Relevance',
    directness: 'Directness',
    independence: 'Independence',
    recency: 'Recency',
    bias_risk: 'Bias risk',
  };
  return Object.entries(labels)
    .map(([key, label]) => typeof factors[key] === 'number' ? `${label}: ${score(factors[key], 5)}` : '')
    .filter(Boolean);
}

export function fileSafe(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 72) || 'evidrai-report';
}

export function reportMarkdown(report: AssessmentResponse) {
  const sources = (report.sources || []).map((source, index) => {
    const label = sourceLabel(source, index);
    const summary = source.summary || source.classification_reason || '';
    const factorLines = sourceScoreFactors(source);
    return `### ${index + 1}. ${label}\n\n` +
      `${summary ? `${summary}\n\n` : ''}` +
      `${linesToMarkdown([
        source.url ? `URL: ${source.url}` : '',
        source.domain ? `Domain: ${source.domain}` : '',
        source.source_type ? `Type: ${source.source_type}` : '',
        source.stance ? `Stance: ${source.stance}` : '',
        source.evidence_category ? `Evidence category: ${source.evidence_category}` : '',
        score(source.score, 5) ? `Source score: ${score(source.score, 5)}` : '',
        source.classification_reason ? `Classification: ${source.classification_reason}` : '',
        ...factorLines,
      ])}`;
  }).join('\n\n');

  const breakdown = (report.claim_breakdown || []).map((item) => (
    `- **${item.text}**: ${item.assessment} (${item.confidence})${item.rationale ? ` — ${item.rationale}` : ''}`
  )).join('\n');

  return `# Evidrai report\n\n` +
    `## Claim\n\n${safe(report.request.claim) || 'Untitled claim'}\n\n` +
    `## Verdict\n\n${safe(report.verdict.label)} · ${safe(report.verdict.confidence)} confidence\n\n` +
    `${safe(report.verdict.summary)}\n\n` +
    `${report.verdict.key_caveat ? `**Key caveat:** ${report.verdict.key_caveat}\n\n` : ''}` +
    `## Metadata\n\n${linesToMarkdown([
      `Assessment ID: ${report.assessment_id}`,
      `Created: ${report.created_at}`,
      `Mode: ${report.mode}`,
      `Schema version: ${report.schema_version}`,
      `Build: ${report.build}`,
      `Source URL: ${report.request.source_url || ''}`,
    ])}\n\n` +
    `${breakdown ? `## Claim breakdown\n\n${breakdown}\n\n` : ''}` +
    `## Evidence sources\n\n${sources || 'No sources recorded.'}\n`;
}

export function journalistBriefMarkdown(report: AssessmentResponse) {
  const primaryOrHighValue = (report.sources || [])
    .filter((source) => ['primary', 'scientific', 'government', 'legal'].includes((source.source_type || '').toLowerCase()) || (source.score || 0) >= 4)
    .slice(0, 8);
  const contradictions = (report.sources || [])
    .filter((source) => ['contradicts', 'contradicting', 'opposes', 'refutes'].some((term) => `${source.stance} ${source.evidence_category}`.toLowerCase().includes(term)))
    .slice(0, 5);
  const sourceRows = (report.sources || []).slice(0, 20).map((source, index) => (
    `| ${index + 1} | ${markdownEscape(sourceLabel(source, index))} | ${markdownEscape(source.source_type || 'source')} | ${markdownEscape(source.stance || '')} | ${markdownEscape(score(source.score, 5) || '')} | ${markdownEscape(source.url || '')} |`
  )).join('\n');
  const caveats = [
    report.verdict.key_caveat,
    !(report.sources || []).length ? 'No sources were recorded with this report.' : '',
    !primaryOrHighValue.length ? 'No direct primary/high-authority source was clearly identified in the saved evidence set.' : '',
  ].filter(Boolean);

  return `# Evidrai journalist brief\n\n` +
    `## Editorial summary\n\n` +
    `${normaliseWhitespace(report.verdict.summary || report.verdict.label || 'No summary recorded.')}\n\n` +
    `## Claim checked\n\n${safe(report.request.claim) || 'Untitled claim'}\n\n` +
    `## Current assessment\n\n${linesToMarkdown([
      `Verdict: ${safe(report.verdict.label)}`,
      `Confidence: ${safe(report.verdict.confidence)}`,
      score(report.verdict.evidence_strength_score, 10) ? `Evidence score: ${score(report.verdict.evidence_strength_score, 10)}` : '',
      `Sources reviewed: ${(report.sources || []).length}`,
    ])}\n\n` +
    `${caveats.length ? `## Caveats / editorial cautions\n\n${linesToMarkdown(caveats)}\n\n` : ''}` +
    `${primaryOrHighValue.length ? `## Strongest source trail\n\n${primaryOrHighValue.map((source, index) => `${index + 1}. ${sourceLabel(source, index)}${source.url ? ` — ${source.url}` : ''}\n   - ${source.summary || source.classification_reason || 'No summary recorded.'}`).join('\n')}\n\n` : ''}` +
    `${contradictions.length ? `## Contradictory or cautionary sources\n\n${contradictions.map((source, index) => `${index + 1}. ${sourceLabel(source, index)}${source.url ? ` — ${source.url}` : ''}\n   - ${source.summary || source.classification_reason || 'No summary recorded.'}`).join('\n')}\n\n` : ''}` +
    `${report.claim_breakdown?.length ? `## Claim breakdown\n\n${report.claim_breakdown.map((item) => `- **${item.text}**: ${item.assessment} (${item.confidence})${item.rationale ? ` — ${item.rationale}` : ''}`).join('\n')}\n\n` : ''}` +
    `## Source table\n\n| # | Source | Type | Stance | Score | URL |\n|---|---|---|---|---|---|\n${sourceRows || '| - | No sources recorded | - | - | - | - |'}\n\n` +
    `## Reproducibility metadata\n\n${linesToMarkdown([
      `Assessment ID: ${report.assessment_id}`,
      `Created: ${report.created_at}`,
      `Mode: ${report.mode}`,
      `Schema version: ${report.schema_version}`,
      `Build: ${report.build}`,
      `Source URL: ${report.request.source_url || ''}`,
    ])}\n\n` +
    `Generated by Evidrai. Treat as a reporting aid, not a substitute for editorial verification.\n`;
}

export function evidencePacketJson(report: AssessmentResponse) {
  return JSON.stringify(report, null, 2);
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
