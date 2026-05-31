export type PolicySection = {
  heading: string;
  paragraphs?: string[];
  bullets?: string[];
};

export type PolicyPage = {
  slug: string;
  group: 'Legal' | 'Trust';
  title: string;
  intro: string;
  summary?: string[];
  sections: PolicySection[];
  contact?: string;
  legalReviewNote?: boolean;
};

export const legalLinks = [
  { href: '/privacy-policy', label: 'Privacy Policy' },
  { href: '/terms-of-use', label: 'Terms of Use' },
  { href: '/cookie-policy', label: 'Cookie Policy' },
  { href: '/ai-disclaimer', label: 'AI Disclaimer' },
  { href: '/acceptable-use', label: 'Acceptable Use Policy' },
  { href: '/copyright-policy', label: 'Copyright Policy' },
];

export const trustLinks = [
  { href: '/confidentiality', label: 'Confidentiality Commitment' },
  { href: '/trust-principles', label: 'Trust Principles' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/appeals', label: 'Appeals Process' },
  { href: '/bias-and-fairness', label: 'Bias & Fairness' },
  { href: '/how-evidrai-works', label: 'How Evidrai Works' },
];

export const policies: PolicyPage[] = [
  {
    slug: 'privacy-policy',
    group: 'Legal',
    title: 'Evidrai Privacy Policy',
    intro: 'How Evidrai collects, uses, protects, and handles personal information across the Services.',
    legalReviewNote: true,
    contact: 'privacy@evidrai.com',
    summary: [
      'We collect only the information needed to operate Evidrai, provide verification services, improve the platform, and protect users.',
      'We do not sell your personal information.',
      'We may use AI systems to analyze content submitted for verification.',
      'You may request access to, correction of, or deletion of your personal data where permitted by law.',
      'We take reasonable steps to protect your information, but no online service can guarantee absolute security.',
    ],
    sections: [
      { heading: '1. Introduction', paragraphs: ['Evidrai ("Evidrai", "we", "our", or "us") is committed to protecting your privacy and handling personal information responsibly.', 'This Privacy Policy explains how we collect, use, disclose, and protect information when you access or use our website, browser extensions, APIs, applications, and related services, collectively referred to as the "Services".', 'By using our Services, you acknowledge the practices described in this Privacy Policy.'] },
      { heading: '2. Information We Collect', paragraphs: ['Information you provide may include name, email address, account credentials, organization name, verification requests, support requests, and content submitted for analysis or verification.', 'Information collected automatically may include IP address, device information, browser information, operating system information, usage analytics, session data, and diagnostic logs.', 'To support verification and credibility analysis, we may collect publicly available information from news organizations, government databases, academic publications, public websites, and social media platforms where permitted.'] },
      { heading: '3. How We Use Information', bullets: ['Provide and operate our Services', 'Generate credibility assessments', 'Improve verification accuracy', 'Prevent fraud and abuse', 'Monitor platform performance', 'Communicate with users', 'Comply with legal obligations', 'Improve our products and services'], paragraphs: ['We do not sell personal information to advertisers.'] },
      { heading: '4. AI Processing', paragraphs: ['Information submitted to Evidrai may be processed by artificial intelligence systems.', 'Such processing may include fact verification, source validation, credibility analysis, content classification, authenticity assessment, and confidence scoring.', 'AI-generated outputs are advisory in nature and should not be relied upon as legal, medical, financial, or professional advice.'] },
      { heading: '5. Data Retention', paragraphs: ['We retain information only as long as necessary to provide Services, protect platform security, improve service quality, and comply with legal obligations.', 'Retention periods may vary depending on the nature of the data and applicable laws.'] },
      { heading: '6. Data Security', bullets: ['Encryption in transit', 'Access controls', 'Authentication mechanisms', 'Monitoring and logging', 'Security reviews'], paragraphs: ['No security system is completely secure, and we cannot guarantee absolute protection.'] },
      { heading: '7. International Data Transfers', paragraphs: ['Your information may be processed in countries outside your country of residence.', 'Where required, Evidrai implements appropriate safeguards designed to comply with applicable privacy laws including GDPR requirements.'] },
      { heading: '8. Your Rights', bullets: ['Access personal information', 'Correct inaccurate information', 'Request deletion', 'Restrict processing', 'Object to processing', 'Request data portability'], paragraphs: ['Requests may be submitted to privacy@evidrai.com.'] },
      { heading: '9. Cookies', paragraphs: ['Evidrai may use cookies and similar technologies to maintain sessions, improve user experience, analyze usage patterns, and enhance security.', 'Users may control cookie preferences through browser settings.'] },
      { heading: '10. Changes to this Policy', paragraphs: ['We may update this Privacy Policy from time to time. Changes become effective when posted on this page.'] },
      { heading: '11. Contact', paragraphs: ['Privacy inquiries may be directed to privacy@evidrai.com.'] },
    ],
  },
  {
    slug: 'terms-of-use', group: 'Legal', title: 'Evidrai Terms of Use', intro: 'The rules for accessing and using Evidrai services, APIs, applications, and website.', legalReviewNote: true, contact: 'legal@evidrai.com',
    summary: ['Evidrai helps users evaluate information, but we do not guarantee that every result is correct.', 'You remain responsible for decisions you make using our platform.', 'Do not use Evidrai for illegal activity, harassment, abuse, malware, manipulation, or attempts to interfere with the platform.', 'You own the content you submit.', 'Evidrai owns the platform, technology, brand, software, and verification systems.'],
    sections: [
      { heading: '1. Acceptance of Terms', paragraphs: ['By accessing or using Evidrai\'s services, website, browser extensions, APIs, or applications, you agree to these Terms of Use.', 'If you do not agree, you must not use the Services.'] },
      { heading: '2. Description of Services', paragraphs: ['Evidrai provides AI-assisted credibility, authenticity, verification, and contextual analysis services.', 'The Services are designed to assist users in evaluating information but do not constitute definitive determinations of truth, legality, or factual accuracy.'] },
      { heading: '3. Eligibility', paragraphs: ['You must be at least 18 years old or the age of legal majority in your jurisdiction to use the Services.'] },
      { heading: '4. User Responsibilities', bullets: ['Violate applicable laws', 'Submit unlawful content', 'Upload malware or malicious code', 'Attempt unauthorized access', 'Interfere with platform operations', 'Reverse engineer Evidrai systems', 'Use the Services to harass or harm others', 'Manipulate or attempt to game credibility assessments'], paragraphs: ['You agree not to use Evidrai for the prohibited activities listed below.'] },
      { heading: '5. User Content', paragraphs: ['Users retain ownership of content submitted to Evidrai.', 'By submitting content, you grant Evidrai a limited license to process, analyze, store, and display that content solely for the purpose of providing the Services.'] },
      { heading: '6. Intellectual Property', paragraphs: ['All Evidrai software, branding, algorithms, methodologies, documentation, and platform features remain the exclusive property of Evidrai unless otherwise stated.', 'No rights are granted except as expressly provided in these Terms.'] },
      { heading: '7. AI-Generated Results', bullets: ['AI systems may produce inaccuracies', 'Results should be independently evaluated', 'Evidrai does not guarantee correctness', 'Assessments may change when new information becomes available'], paragraphs: ['Verification scores, credibility assessments, explanations, and recommendations generated by Evidrai are probabilistic outputs.'] },
      { heading: '8. Disclaimer of Warranties', paragraphs: ['The Services are provided "AS IS" and "AS AVAILABLE."', 'Evidrai disclaims all warranties, express or implied, including warranties of merchantability, fitness for a particular purpose, and non-infringement.'] },
      { heading: '9. Limitation of Liability', bullets: ['Indirect damages', 'Consequential damages', 'Reputational harm', 'Lost profits', 'Loss of data', 'Decisions made based on platform outputs'], paragraphs: ['To the maximum extent permitted by law, Evidrai shall not be liable for the categories listed below.'] },
      { heading: '10. No Sole Reliance', paragraphs: ['Users agree not to rely solely on Evidrai outputs when making legal, financial, medical, employment, regulatory, reputational, or other significant decisions.'] },
      { heading: '11. Termination', paragraphs: ['Evidrai may suspend or terminate access to the Services at any time for violations of these Terms or to protect the platform and its users.'] },
      { heading: '12. Changes to the Services', paragraphs: ['We reserve the right to modify, suspend, or discontinue any part of the Services at any time.'] },
      { heading: '13. Governing Law', paragraphs: ['These Terms shall be governed by the laws of the jurisdiction in which Evidrai is incorporated.'] },
      { heading: '14. Contact', paragraphs: ['Questions regarding these Terms may be directed to legal@evidrai.com.'] },
    ],
  },
  {
    slug: 'confidentiality', group: 'Trust', title: 'Evidrai Confidentiality & Data Handling Commitment', intro: 'How Evidrai treats submitted materials, confidential content, and AI-assisted processing.', contact: 'trust@evidrai.com',
    summary: ['Your content belongs to you.', 'We treat submitted materials as confidential.', 'We do not sell submitted content.', 'We do not use submitted content to train public AI models without permission.', 'We strive to explain how our AI reaches conclusions whenever possible.'],
    sections: [
      { heading: 'Because Trust Needs Evidence', paragraphs: ['Trust is the foundation of Evidrai.', 'We recognize that users may submit sensitive information for analysis, verification, and credibility assessment. This document outlines our commitment to confidentiality and responsible data handling.'] },
      { heading: 'Ownership of Submitted Content', paragraphs: ['Users retain ownership of all content submitted to Evidrai.', 'Submission of content does not transfer ownership rights to Evidrai.'] },
      { heading: 'Confidential Processing', bullets: ['Draft articles', 'Research papers', 'Internal reports', 'Screenshots', 'Communications', 'Evidence packages', 'Business documents'], paragraphs: ['Submitted materials may include sensitive or confidential information.', 'Evidrai treats submitted materials as confidential and limits access to systems and personnel necessary to provide the Services.'] },
      { heading: 'Restricted Access', bullets: ['Role-based access controls', 'Authentication requirements', 'Audit logging', 'Security monitoring'], paragraphs: ['Access to submitted content is restricted using technical and organizational safeguards.'] },
      { heading: 'AI Model Training Commitment', bullets: ['Submitted content will not be used to train public AI models unless expressly authorized by the customer.', 'Submitted content will not be sold.', 'Submitted content will not be licensed to third parties.', 'Submitted content will not be shared with advertisers.'] },
      { heading: 'Transparency', bullets: ['Supporting evidence', 'Source attribution', 'Confidence indicators', 'Explanations of conclusions'], paragraphs: ['Where AI contributes to an assessment, Evidrai strives to provide transparency so users can understand how assessments are generated whenever reasonably possible.'] },
      { heading: 'Human Accountability', paragraphs: ['Artificial intelligence is a tool, not a final authority.', 'Evidrai believes important decisions should remain subject to human judgment and review.'] },
      { heading: 'Security', paragraphs: ['Evidrai continuously works to protect user information through industry-standard security practices and ongoing improvements.'] },
      { heading: 'Contact', paragraphs: ['Questions regarding confidentiality may be directed to trust@evidrai.com.'] },
    ],
  },
  {
    slug: 'ai-disclaimer', group: 'Legal', title: 'Evidrai AI Disclaimer', intro: 'Important information about the limits of AI-assisted credibility and verification assessments.', legalReviewNote: true,
    summary: ['Evidrai uses AI to help assess credibility, authenticity, and context.', 'AI can make mistakes.', 'Evidrai does not determine absolute truth.', 'Our outputs should be treated as evidence-based decision support, not final judgments.', 'Users should review the supporting evidence and use their own judgment, especially for important decisions.'],
    sections: [
      { heading: 'Important Information About Evidrai Assessments', paragraphs: ['Evidrai uses artificial intelligence to assist with credibility analysis, source verification, and contextual evaluation of information.', 'While we strive for accuracy, AI systems have limitations.'] },
      { heading: 'Evidrai Does Not Determine Truth', paragraphs: ['Evidrai provides evidence-based assessments and confidence indicators.', 'Our outputs are intended to help users evaluate information but should not be interpreted as definitive statements of fact, truth, legality, or authenticity.'] },
      { heading: 'AI Can Be Wrong', bullets: ['Produce inaccurate conclusions', 'Miss relevant information', 'Misinterpret context', 'Generate incomplete analyses', 'Overstate or understate confidence'], paragraphs: ['Like all AI systems, Evidrai may make mistakes.', 'Users should independently review supporting evidence before making important decisions.'] },
      { heading: 'Not Professional Advice', bullets: ['Legal advice', 'Medical advice', 'Financial advice', 'Regulatory guidance', 'Professional investigative services', 'Employment screening', 'Law enforcement investigation'], paragraphs: ['Evidrai is not a substitute for professional advice or official investigation.'] },
      { heading: 'Reputation Impact Disclaimer', paragraphs: ['Evidrai assessments represent probabilistic analyses generated using available information and should not be interpreted as definitive judgments regarding any person, organization, product, publication, or claim.'] },
      { heading: 'Human Judgment Remains Essential', paragraphs: ['Evidrai is designed to support human decision-making, not replace it.', 'Users remain responsible for decisions made based on information provided by the platform.'] },
      { heading: 'Continuous Improvement', paragraphs: ['Our models, methodologies, and verification systems are continuously evolving.', 'Assessments may change as new information becomes available.', 'Because trust needs evidence.'] },
    ],
  },
  {
    slug: 'trust-principles', group: 'Trust', title: 'Evidrai Trust Principles', intro: 'The principles guiding Evidrai product, methodology, privacy, transparency, and accountability decisions.',
    sections: [
      { heading: 'Because Trust Needs Evidence', paragraphs: ['Evidrai exists to help people evaluate information using evidence, transparency, and accountability.', 'Our principles guide every product decision we make.'] },
      { heading: 'Evidence Before Opinion', paragraphs: ['Credibility assessments should be grounded in verifiable evidence, not ideology, popularity, or authority alone.'] },
      { heading: 'Transparency Over Black Boxes', paragraphs: ['Users deserve to understand why a conclusion was reached.', 'Whenever possible, Evidrai provides supporting sources, confidence indicators, and explanations.'] },
      { heading: 'Human Judgment Matters', paragraphs: ['AI can assist decision-making but should not replace human reasoning.', 'Evidrai is designed to support informed decisions, not make decisions on behalf of users.'] },
      { heading: 'Independence', paragraphs: ['Evidrai does not adjust credibility assessments based on political affiliation, commercial interests, advertiser influence, or popularity.'] },
      { heading: 'Accountability', paragraphs: ['We acknowledge that AI systems can make mistakes.', 'When errors are identified, we aim to correct them transparently and continuously improve our systems.'] },
      { heading: 'Privacy by Design', paragraphs: ['Trust requires responsible handling of information.', 'We strive to minimize data collection, protect user privacy, and give users control over their information.'] },
      { heading: 'Continuous Improvement', paragraphs: ['Truth-seeking is an ongoing process.', 'We are committed to refining our methodologies, improving transparency, and incorporating new evidence as it becomes available.'] },
      { heading: 'Our Mission', paragraphs: ['To make evidence easier to find, credibility easier to assess, and trust easier to earn.', 'Because trust needs evidence.'] },
    ],
  },
  {
    slug: 'cookie-policy', group: 'Legal', title: 'Evidrai Cookie Policy', intro: 'How Evidrai may use cookies and similar technologies across the website and Services.', legalReviewNote: true, contact: 'privacy@evidrai.com',
    summary: ['Evidrai may use cookies to keep the site working, improve user experience, understand usage, and protect the platform.', 'Some cookies are essential. Others, such as analytics cookies, may be optional depending on your location and preferences.', 'You can manage cookies through your browser settings or through any cookie preference tool provided on the site.'],
    sections: [
      { heading: '1. What Are Cookies?', paragraphs: ['Cookies are small text files stored on your device when you visit a website.', 'They help websites remember information about your visit, such as preferences, session status, and usage patterns.'] },
      { heading: '2. How Evidrai Uses Cookies', bullets: ['Operate the website', 'Maintain user sessions', 'Improve site performance', 'Understand usage patterns', 'Enhance security', 'Remember user preferences'] },
      { heading: '3. Types of Cookies We May Use', paragraphs: ['Essential cookies are necessary for the website and Services to function properly. They may support login, security, routing, and session management.', 'Analytics cookies help us understand how users interact with Evidrai so we can improve the product.', 'Performance cookies help us monitor site speed, reliability, and technical performance.', 'Preference cookies help remember user choices, such as language or display preferences.', 'Some third-party services may set cookies where integrated into the site, such as analytics, embedded content, or support tools.'] },
      { heading: '4. Managing Cookies', paragraphs: ['You can control cookies through your browser settings.', 'Where legally required, Evidrai will provide cookie consent options.', 'Disabling some cookies may affect site functionality.'] },
      { heading: '5. Changes to this Policy', paragraphs: ['We may update this Cookie Policy from time to time. Changes become effective when posted on this page.'] },
      { heading: '6. Contact', paragraphs: ['Questions may be directed to privacy@evidrai.com.'] },
    ],
  },
  {
    slug: 'acceptable-use', group: 'Legal', title: 'Evidrai Acceptable Use Policy', intro: 'How users may and may not use Evidrai.', legalReviewNote: true, contact: 'legal@evidrai.com',
    summary: ['Use Evidrai responsibly.', 'Do not use the platform to break the law, harass people, upload malware, manipulate assessments, or abuse the system.', 'We may suspend or terminate accounts that misuse the platform.'],
    sections: [
      { heading: '1. Purpose', paragraphs: ['This Acceptable Use Policy explains how users may and may not use Evidrai.', 'It is designed to protect users, the platform, and the integrity of Evidrai assessments.'] },
      { heading: '2. Prohibited Uses', bullets: ['Violate laws or regulations', 'Harass, threaten, or abuse others', 'Upload malware, spyware, or malicious code', 'Attempt unauthorized access to systems', 'Interfere with platform operations', 'Reverse engineer the Services', 'Misrepresent Evidrai outputs', 'Manipulate or game credibility scores', 'Generate or support disinformation campaigns', 'Submit content you do not have the right to use', 'Conduct unlawful surveillance', 'Impersonate another person or organization'] },
      { heading: '3. Abuse of AI Systems', paragraphs: ['You may not attempt to exploit, prompt-inject, manipulate, or bypass Evidrai\'s AI systems, safety controls, scoring logic, or verification methods.'] },
      { heading: '4. Enforcement', bullets: ['Remove content', 'Restrict access', 'Suspend accounts', 'Terminate accounts', 'Report unlawful activity where required'], paragraphs: ['Evidrai may investigate suspected violations and take action where appropriate.'] },
      { heading: '5. Contact', paragraphs: ['Questions about acceptable use may be directed to legal@evidrai.com.'] },
    ],
  },
  {
    slug: 'copyright-policy', group: 'Legal', title: 'Evidrai Copyright and DMCA Policy', intro: 'How rights holders can submit copyright complaints and counter-notices.', legalReviewNote: true, contact: 'copyright@evidrai.com',
    summary: ['Evidrai respects intellectual property rights.', 'If you believe copyrighted material has been used improperly through our Services, you may submit a copyright complaint.', 'If your content was removed in error, you may submit a counter-notice where permitted by law.'],
    sections: [
      { heading: '1. Respect for Copyright', paragraphs: ['Evidrai respects the intellectual property rights of creators, publishers, researchers, and rights holders.', 'Users are responsible for ensuring they have appropriate rights to submit content to the Services.'] },
      { heading: '2. Copyright Complaints', bullets: ['Your name and contact information', 'Identification of the copyrighted work', 'Identification of the allegedly infringing material', 'A statement that you believe the use is unauthorized', 'A statement that the information in your notice is accurate', 'Your physical or electronic signature'], paragraphs: ['If you believe your copyrighted work has been infringed, please send a notice containing the information below.', 'Notices may be sent to copyright@evidrai.com.'] },
      { heading: '3. Counter-Notices', bullets: ['Your name and contact information', 'Identification of the removed or restricted material', 'A statement explaining why you believe the action was mistaken', 'Your physical or electronic signature'], paragraphs: ['If you believe material was removed or restricted in error, you may submit a counter-notice where permitted by law.'] },
      { heading: '4. Repeat Infringers', paragraphs: ['Evidrai may suspend or terminate accounts of users who repeatedly infringe intellectual property rights.'] },
      { heading: '5. Contact', paragraphs: ['Copyright inquiries may be directed to copyright@evidrai.com.'] },
    ],
  },
  {
    slug: 'methodology', group: 'Trust', title: 'Evidrai Methodology Transparency Statement', intro: 'How Evidrai approaches credibility and verification methodology.', contact: 'trust@evidrai.com',
    summary: ['Evidrai evaluates information using evidence, source quality, context, consistency, and confidence indicators.', 'We aim to explain why a result was produced.', 'Our methodology will continue to evolve as the platform improves.'],
    sections: [
      { heading: '1. Purpose', paragraphs: ['This statement explains the principles behind Evidrai\'s credibility and verification methodology.', 'Evidrai is designed to help users understand information more clearly by examining available evidence and context.'] },
      { heading: '2. Evidence-Based Assessment', bullets: ['Source attribution', 'Source credibility', 'Corroborating evidence', 'Contradictory evidence', 'Publication history', 'Context', 'Claim specificity', 'Timeliness of information', 'Publicly available records', 'Expert or institutional references where available'], paragraphs: ['Evidrai assessments may consider a range of evidence and context signals.'] },
      { heading: '3. Confidence Indicators', bullets: ['Quantity of available evidence', 'Quality of sources', 'Agreement between sources', 'Recency of information', 'Ambiguity or uncertainty', 'Availability of primary evidence'], paragraphs: ['Evidrai may present confidence levels to indicate how strongly available evidence supports an assessment.'] },
      { heading: '4. Limits of Methodology', paragraphs: ['Evidrai may not always have access to all relevant information.', 'Assessments may be incomplete where evidence is missing, conflicting, private, newly emerging, or difficult to verify.'] },
      { heading: '5. Source Transparency', paragraphs: ['Where possible, Evidrai aims to provide supporting sources or explanations so users can review the basis of an assessment.'] },
      { heading: '6. Updates', paragraphs: ['Assessments may change as new evidence becomes available.', 'Evidrai is committed to continuous improvement of its methods, models, and transparency practices.'] },
      { heading: '7. Contact', paragraphs: ['Questions about methodology may be directed to trust@evidrai.com.'] },
    ],
  },
  {
    slug: 'appeals', group: 'Trust', title: 'Evidrai Appeals Process', intro: 'How users and affected parties can challenge or request review of an Evidrai assessment.', contact: 'trust@evidrai.com',
    summary: ['If you believe an Evidrai assessment is wrong, incomplete, or unfair, you may submit additional evidence for review.', 'Evidrai may update an assessment where appropriate.', 'AI systems can miss context, and we believe users should have a fair way to challenge important outputs.'],
    sections: [
      { heading: '1. Purpose', paragraphs: ['Evidrai provides AI-assisted credibility and verification assessments.', 'Because assessments may affect how information is interpreted, we provide a process for users to challenge or request review of an assessment.'] },
      { heading: '2. Who May Submit an Appeal?', bullets: ['A user who requested the assessment', 'A person or organization referenced in an assessment', 'A rights holder or authorized representative', 'Another party with relevant evidence'] },
      { heading: '3. Grounds for Appeal', bullets: ['Factually inaccurate', 'Based on incomplete information', 'Missing relevant evidence', 'Misinterpreting context', 'Outdated', 'Potentially biased or unfair'] },
      { heading: '4. How to Submit an Appeal', bullets: ['The assessment or result being challenged', 'A clear explanation of the concern', 'Supporting evidence or sources', 'Contact information', 'Any urgency or potential harm'], paragraphs: ['Appeals may be sent to trust@evidrai.com.'] },
      { heading: '5. Review Process', bullets: ['Updated', 'Clarified', 'Corrected', 'Withdrawn', 'Left unchanged'], paragraphs: ['Evidrai may review submitted information and determine whether the assessment should be changed.'] },
      { heading: '6. No Guaranteed Outcome', paragraphs: ['Submitting an appeal does not guarantee that an assessment will be changed.', 'However, Evidrai will consider relevant evidence in good faith.'] },
      { heading: '7. Continuous Improvement', paragraphs: ['Appeals help Evidrai improve its systems, methodology, and transparency.'] },
    ],
  },
  {
    slug: 'bias-and-fairness', group: 'Trust', title: 'Evidrai Bias & Fairness Statement', intro: 'Evidrai’s commitment to evidence-based, fair, and carefully monitored credibility assessment.', contact: 'trust@evidrai.com',
    summary: ['Evidrai aims to evaluate evidence, not ideology.', 'Credibility assessments should not be based on race, religion, nationality, gender, political affiliation, or protected characteristics.', 'We recognize that AI systems can reflect bias and must be monitored carefully.'],
    sections: [
      { heading: '1. Our Commitment', paragraphs: ['Evidrai is committed to building systems that evaluate claims, sources, and evidence fairly.', 'We aim to avoid unfair treatment of people, organizations, communities, or viewpoints.'] },
      { heading: '2. Evidence, Not Identity', bullets: ['Race', 'Ethnicity', 'Religion', 'Gender', 'Sexual orientation', 'Nationality', 'Disability', 'Political affiliation', 'Protected personal characteristics'], paragraphs: ['Evidrai assessments should be based on available evidence and context, not identity or protected characteristics.'] },
      { heading: '3. Political and Ideological Neutrality', paragraphs: ['Evidrai is designed to assess evidence, not enforce ideology.', 'Political popularity, controversy, or disagreement should not determine credibility.'] },
      { heading: '4. Bias Monitoring', paragraphs: ['We recognize that AI systems may produce biased or uneven outcomes.', 'Evidrai aims to monitor, test, and improve systems to reduce unfair bias.'] },
      { heading: '5. Human Review and Appeals', paragraphs: ['Where appropriate, users may challenge assessments through the Evidrai Appeals Process.', 'Appeals may help identify bias, missing context, or unfair conclusions.'] },
      { heading: '6. Continuous Improvement', paragraphs: ['Fairness is an ongoing responsibility.', 'Evidrai will continue refining its methods as the platform develops.'] },
      { heading: '7. Contact', paragraphs: ['Questions about fairness may be directed to trust@evidrai.com.'] },
    ],
  },
  {
    slug: 'how-evidrai-works', group: 'Trust', title: 'How Evidrai Works', intro: 'A plain-English explanation of the Evidrai assessment flow.',
    summary: ['Evidrai helps users understand whether information is credible by analyzing evidence, sources, context, and uncertainty.', 'The platform does not simply say "true" or "false".', 'It aims to show why an assessment was made and what evidence supports it.'],
    sections: [
      { heading: '1. Submit or Identify Content', paragraphs: ['A user may submit content, a URL, a claim, a screenshot, or other material for review.'] },
      { heading: '2. Identify the Claim', paragraphs: ['Evidrai analyzes the submitted material to identify relevant claims, assertions, sources, or context.'] },
      { heading: '3. Search for Evidence', bullets: ['Public sources', 'News reports', 'Academic sources', 'Government records', 'Trusted databases', 'Source history', 'Corroborating or contradictory evidence'], paragraphs: ['Where available, Evidrai may compare the claim against relevant evidence sources.'] },
      { heading: '4. Assess Source Quality', paragraphs: ['Evidrai may evaluate the quality and reliability of sources based on available signals.', 'These may include transparency, publication history, primary evidence, corrections, and corroboration.'] },
      { heading: '5. Generate an Assessment', bullets: ['A credibility assessment', 'A confidence indicator', 'Supporting evidence', 'Relevant context', 'Limitations or uncertainty'] },
      { heading: '6. Explain the Result', paragraphs: ['Where possible, Evidrai aims to explain why a result was produced.', 'Users should be able to review evidence rather than simply accept a black-box answer.'] },
      { heading: '7. Human Judgment', paragraphs: ['Evidrai is a decision-support tool.', 'Users should review the evidence and apply their own judgment, especially for important decisions.'] },
      { heading: '8. Ongoing Improvement', paragraphs: ['Evidrai\'s methodology, models, and evidence systems will continue to evolve.', 'Because trust needs evidence.'] },
    ],
  },
];

export function policyBySlug(slug: string) {
  return policies.find((policy) => policy.slug === slug);
}
