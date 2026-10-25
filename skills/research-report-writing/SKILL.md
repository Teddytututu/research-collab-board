---
name: research-report-writing
description: Draft or revise research reports, experiment result pages and research-route summaries for collaborators or general readers, in HTML or LaTeX. Use for report writing and revision grounded in supplied research evidence.
---

# Research report writing

[中文规则](references/writing.zh-CN.md)

Organize the report as an argument for its reader. Adapt its structure to the research question and evidence. Keep authorship, numerical results and the strength of claims faithful to supplied material. This skill supports writing and local preparation within the task's authorization; external publication follows the user's chosen workflow.

## 1. Decide what the reader needs

Identify the reader and the four questions they need answered: the research question, the answer, the evidence, and the next step. Lead with these answers rather than the chronological work log. Preserve the researcher's contribution: observations, intuitions, revised hypotheses and theoretical explanations. Read the supplied reasoning alongside experiment records.

When new results change the argument, revise the full narrative. Keep detailed audits, provenance, execution records and per-sample outputs in companion files. Keep the reader-facing report focused on findings and essential scientific context.

## 2. Select content by its evidential value

- Retain comparisons, compute comparisons and examples that let the reader inspect the evidence. Put repair history and item-level records in a separate complete-results page or attachment.
- Give each example a denominator and its prevalence in the evaluated set, when that set supports the claim.
- Match method names to the actual implementation. Separate a published method, a reproduction and an adaptation explicitly. Report relevant negative results and their scope; retain unrelated experiments in the research archive.
- Show scientific value through technical content. Keep task counts, personal workload and staffing in work records.
- Complete inexpensive, authorized follow-up checks before describing them as future work. Scale polishing to the report's remaining use.

## 3. Preserve scientific rigor

- Establish comparable samples, resolution, scoring rules and hardware before comparing results. Explain material differences when an exact match is impractical.
- Separate benchmark scoring for paper comparison from independent judgments of the claimed improvement. Where appropriate, use reviewers blinded to method identity, or a model in a fresh context, and check agreement against human judgments. Restrict conclusions to what the available evaluations support.
- Support causal language with an appropriate experiment. Label hypotheses as possible explanations and state when the cause remains open.
- Compare time on the same hardware and measurement scope; record GPU and CPU costs separately. If accounting choices change the result, give the supported range. Present differing hardware measurements separately.
- Follow the evaluation protocol's treatment of ambiguous samples. Declare it before aggregation; report ambiguous counts and sensitivity when their treatment changes a conclusion. Treat quality scoring and evaluator agreement as separate quantities.
- Report subjective criteria, such as style or realism, separately from objective task correctness.

## 4. Write in a researcher's voice

Use concrete findings, numbers and changes of plan. Prefer affirmative, ordinary language. Give each section a specific informative title, such as “Compute cost and correct answers” or “Hypotheses, experiments and revisions”. Remove slogans and claims of effort.

Every sentence should help the reader understand the work. Keep publication dates, revision commentary and instructions for navigating the report in companion records when they serve only the workflow. Present a main conclusion as a bold sentence followed by two or three sentences of evidence. Include essential scientific definitions and citations according to the requested format; detailed traceability belongs in the companion record.

## 5. Make comparisons visible

- For a comparative claim, show the figure before a precision table. Use counts for tiny groups.
- Give each table one coherent comparison; label reproduced and published results separately, and distinguish counts from scores.
- Assign each method a consistent color across diagrams, charts, annotations and table rows. Use related but distinguishable colors for related methods.
- Place the baseline beside the changed result and the explanation beside its evidence. Keep image and video comparisons adjacent. Put a key count in a short sample heading when useful.
- Put the image behind a visual intuition beside that observation. Keep table cells short. Redesign figures that require a paragraph of decoding; captions should contribute essential context.
- Typeset formulas: native MathML for offline HTML, and compiled math for LaTeX.

## 6. Revise safely

Cold-read the rendered report. For interactive revisions, change the requested passage, refresh and inspect the result. Preserve the previous version before a substantial edit. Replace complete contextual strings rather than short fragments that can alter unrelated numbers. Compare numerical values with the prior version and verify every image's identity.

Synchronize the agreed delivery file, hosted copy and archive when those copies are in scope and authorized. Keep intermediate files in a separate work directory.

## 7. Deliver a usable artifact

For an offline HTML report, inline SVG charts, JPEG images as data URLs and MathML formulas. Retain the requested image quality and use a multi-file package when its size or media requires it. Package a report and complete-results page together with relative links that work offline. For LaTeX, compile the requested output and inspect its rendering.

Give the final artifact's concrete location. Keep logs, checks, provenance and revision notes in companion records. Open or publish only as authorized by the user's task.

## 8. Final reading check

- [ ] The opening answers the reader's research question, result, evidence and next step.
- [ ] The researcher's own reasoning is represented and formulas are typeset.
- [ ] Examples include appropriate denominators; causal claims match their evidence.
- [ ] Comparisons, ambiguity handling and CPU/GPU accounting use explicit scientific definitions.
- [ ] Findings and relevant negative results remain in the report; execution details live in companions.
- [ ] Titles carry information, and the prose uses concrete research language.
- [ ] Color assignments and adjacent comparisons remain consistent.
- [ ] Numbers match source evidence, and every figure is the intended figure.
- [ ] The rendered artifact and its offline links work; agreed copies are synchronized.

## Optional HTML helper

[templates/report_helpers.py](templates/report_helpers.py) uses only the Python standard library. It provides inline SVG bars, lines, a timeline, phase blocks, JPEG embedding and a MathML example. Run it in a temporary output directory to create `report.html`, then replace its explicitly illustrative data with supplied evidence. The helper's functions are optional building blocks; choose the layout that fits the argument.
