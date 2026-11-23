# US payrolls rose by 73,000. Why was the published level 185,000 below June’s first estimate?

*StatGazer methods note*

| A · June 2025, first estimate | B · June 2025, revised estimate | C · July 2025, first estimate |
|---|---|---|
| **159,724,000 jobs** | **159,466,000 jobs** | **159,539,000 jobs** |
| July 3, 2025 release | August 1, 2025 release | August 1, 2025 release |

These are seasonally adjusted US nonfarm payroll jobs. The Bureau of Labor Statistics (BLS) lowered its June estimate by 258,000 jobs. July’s gain of 73,000 from revised June closed only part of that gap (+73,000 − 258,000 = −185,000 jobs). [July 3, Table B-1](https://www.bls.gov/news.release/archives/empsit_07032025.htm) · [August 1, Table B-1](https://www.bls.gov/news.release/archives/empsit_08012025.htm)

**Month-on-month change.** “In its August 1, 2025 release, BLS estimated that US nonfarm payrolls rose by 73,000 jobs from June to July, using the revised June level.”

**Change since the previous release.** “The July payroll level published on August 1, 2025 was 185,000 jobs below the first June estimate published on July 3.”

## The same distinction in industrial production

The Federal Reserve’s January 17, 2024 release put December industrial production at 102.5 (seasonally adjusted, 2017 = 100). On February 15 the Fed revised December to 102.7 and put January at 102.6. January was **down 0.1 index point** from revised December and **up 0.1 index point** from the December level clients had seen on January 17. [January 17, G.17 summary](https://www.federalreserve.gov/releases/g17/20240117/g17.txt) · [February 15, G.17 summary](https://www.federalreserve.gov/releases/g17/20240215/g17.txt)

## What the model reported

Before querying the model, we selected seven pairs of consecutive releases using their published values. In four, the two correct directions were opposite. Three were same-direction controls with small or zero revisions at the printed precision. This selection tests a known difficulty and cannot estimate its frequency in routine releases.

We asked Qwen3-4B each question separately in Russian, with the same table extracts, three labeled levels and all three signed differences. The second version of the prompt explicitly stated that the monthly change plus the prior-month revision equals the change across releases. In **each of the four opposite-sign pairs**, the model gave both questions the same direction under each prompt. In each condition it answered all eight questions and gave four wrong directions. In both payroll cases where the two questions required opposite directions, adding the explanation fixed the model’s sign error for the monthly change and introduced one for the change since the previous release. A calculation with a sentence template gave the correct direction on all eight, and on all 14 questions overall. [Pilot results](results.md)

Asked about the July payroll change **within** the August release, the model gave this reply to the direct prompt.

> Ниже на 73 thousand jobs.  
> Ячейки: C − B = +73.

“Ниже” means “lower.” The model identified July and revised June, repeated the correct signed difference, and told the client the level had fallen. [Saved response](model/responses/3d765f7ee428.json)

Run `./reproduce.sh` in the pilot folder to re-extract the table rows from 14 archived releases, rebuild the reference answers and prompts, and verify the scores against the saved replies and blinded ratings. This offline check uses the original replies without generating new ones.

**When to reopen the research question.** Revisit a journal study only when we have real requests that leave the baseline unstated. Test when an assistant can infer that intent and when the analyst is better served by seeing both changes or by answering one clarifying question. The reference must be the request author’s own confirmed intent, recorded before they see any candidate answer.

**Analyst’s rule.** Fix the comparison baseline before drafting the comment. In the client sentence, name the reference period, the release date and the units. When comparing two releases, give both dates.
