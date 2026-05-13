# Evidrai User Test Plan

Date: 2026-05-10

## Purpose

Run a lightweight external user test to understand whether Evidrai is clear, useful, trustworthy, and easy to use for a first-time tester.

## Test Goals

1. Check whether the tester understands what Evidrai does within 30 seconds.
2. Validate whether the verdict language is clear and credible.
3. Identify where users are confused by evidence, confidence, source cards, or caveats.
4. Test whether Fast vs Deep mode feels useful.
5. Gather concrete improvement feedback before further feature work.

## Tester Profile

Ideal first tester:

- Smart non-builder user
- Comfortable using web apps
- Interested in news, AI, misinformation, or trust online
- Willing to give blunt feedback
- Not too close to the project, so first impressions are real

## Test Setup

Send tester:

- App link
- Short explanation of Evidrai
- 3 to 5 test tasks
- Feedback form/questions
- Expected time: 20 to 30 minutes

## Suggested Invite Message

Hi [Name],

I’m testing a small prototype called Evidrai. It checks claims, headlines, posts, or article snippets and tries to explain how strong the evidence is, not just whether something sounds plausible.

Would you be willing to spend 20–30 minutes trying it and giving blunt feedback?

What I’d like you to do:

1. Open the app: [APP LINK]
2. Try 3–5 claims/headlines/posts of your choice
3. Use at least one claim where you already have an opinion
4. Use one claim where you genuinely don’t know the answer
5. Send feedback using the questions below

I’m especially interested in where the app is confusing, overconfident, slow, unclear, or genuinely useful.

Thanks — honest criticism is more useful than politeness here.

## Test Tasks

Ask the tester to try:

1. A current news headline or claim
2. A social-media-style rumour
3. A health/science claim
4. A political or public figure claim
5. One deliberately vague or opinion-heavy claim

For each test, ask them to note:

- Input used
- Mode used: Fast / Deep / Auto
- Whether the result felt clear
- Whether they trusted the verdict
- Whether the evidence explanation helped
- Anything confusing or missing

## Feedback Questions

### First impression

1. In one sentence, what do you think Evidrai does?
2. Was the app’s purpose clear immediately?
3. What, if anything, felt confusing before you entered a claim?

### Result quality

4. Did the verdict make sense?
5. Did the confidence level feel justified?
6. Did the explanation separate evidence from speculation clearly?
7. Were the sources useful?
8. Did the app ever feel overconfident?
9. Did it ever feel too cautious or non-committal?

### UX

10. Was anything too slow?
11. Was there too much information, too little, or about right?
12. Which section was most useful?
13. Which section would you remove or simplify?

### Trust

14. Would you use this before sharing or believing a claim?
15. What would make you trust it more?
16. What would make you distrust it?

### Product direction

17. What is the most valuable use case you can imagine?
18. Who would benefit most from this?
19. What would you expect this to become: browser extension, website, API, social media tool, something else?
20. Would you use it again? Why or why not?

## Feedback Capture Format

Preferred structure:

```text
Tester:
Date:
App link tested:

Overall score /10:
Would use again? Yes/No/Maybe

Top 3 positives:
1.
2.
3.

Top 3 problems:
1.
2.
3.

Most confusing result:

Most useful result:

Feature requests:

Raw notes:
```

## Follow-up Process

1. Invite tester.
2. Confirm they can access the app.
3. Ask them to complete test within a defined window.
4. Collect feedback.
5. Summarise into:
   - bugs
   - UX issues
   - trust/credibility issues
   - feature ideas
   - priority fixes
6. Add accepted follow-up work to Notion tracker.

## Management Notes

Do not over-explain Evidrai before testing. The first impression is part of the test.

Ask for honest feedback, not validation.

If the tester reports a confusing result, ask for the exact input text and mode used so it can become a regression fixture later.
