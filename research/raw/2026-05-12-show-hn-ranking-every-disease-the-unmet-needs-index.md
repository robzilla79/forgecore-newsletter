# Show HN: Ranking every disease (the unmet needs index)

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 20:43:33 +0000
- URL: https://insights.convoke.bio/unmet-needs
- Domain: insights.convoke.bio
- Tags: builders, tools, indie

## Feed summary

Article URL: https://insights.convoke.bio/unmet-needs
Comments URL: https://news.ycombinator.com/item?id=48114263
Points: 3
# Comments: 0

## Extracted article text

There are thousands of named human diseases, many of which are rare and obscure. Within each disease, there are yet more subsegments of distinct biology that require their own distinct treatments. With so many patients in need of better drugs, it's hard for a drug developer to know which particular problems to focus on.
Because this problem space is so immense, drug developers often focus on solving unmet needs that are visible to them. If you read the history of some of our most impactful therapeutics, it is surprising how often the genesis of an idea can be traced back to a personal story, a patient anecdote, or a passionate clinician who happened to match an unmet need to a potential medicine.
At Convoke, we think that one of the more promising use cases for language models, and artificial intelligence generally, is to scan the entire corpus of human knowledge to help surface overlooked information. One of our goals is to help operationalize biomedical knowledge, and so we've put together this index of unmet needs in human disease. Our hope is that the right person might uncover a worthy problem on this list that they otherwise wouldn't know about, and that regular updates can keep a record of progress against disease over time.
The Convoke team
A list of ~2,400 indications was distilled from multiple public ontologies (e.g. MeSH, ICD10, DiseaseOntology) and manually curated to remove duplicates, anatomical site-specific terms, hyper-rare conditions, or trauma/accidental injuries. Convoke's LLM-based agents then researched each indication, primarily from public sources, and scored each dimension of unmet need below against a defined rubric on a 0 to 7 scale.
- Burden (BUR) Severity of the condition if untreated
- Impact of the disease on how a patient feels, functions, or survives assuming they receive no treatment. Ranges from asymptomatic with no impact (0), to a life expectancy of <1 year or total functional dependence (7). Not used to calculate the overall ranking.
- Efficacy (EFF) Residual burden of disease after optimal SoC
- Same survival/function rubric as burden, but assuming current standard of care (SoC) treatment; higher means more residual burden remains despite treatment.
- Prevalence (PRE) Population scale of need
- Disease prevalence per 100,000, continuously mapped across the dataset from lowest prevalence (0) to highest prevalence (7).
- Safety (SAF) Adverse-event and tolerability burden
- Scores the toxicity, severe-event risk, monitoring, and discontinuation of the standard of care. Scoring ranges from placebo-like (0) to treatment-limiting and potentially life-threatening (7).
- Convenience (CON) Logistical burden of treatment
- Scores route, visit frequency, monitoring, and self-administration complexity, from one-time curative (0) or occasional care through to life- and freedom-dominating regimens (7).
- Pipeline (PIP) Active therapeutic development
- Number of active clinical-stage development programs in the indication, weighted by stage of development and continuously mapped across the dataset from no active clinical-stage programs (0) to the highest number of active programs (7).
The index is calculated as a weighted composite score of all dimensions (excluding burden if untreated) with the below weights
Rank is derived from the resulting composite score: higher unmet need scores are placed higher in the table, and indications with the same composite score share a tied rank.
Caveats
Scores are based on a vignette of a typical patient at diagnosis and do not fully capture subtype-specific burden, biomarker-defined populations, later-line treatment settings, geography-specific access, or other subtype-specific nuances. If you are interested in a custom analysis, we'd be happy to assist.
Lower scores do not imply the absence of unmet need. They may indicate that burden is concentrated in a subgroup or that current care works for many patients. As large language models (LLMs) were used to generate the scores, there may also be errors: please do let us know if you find any.
For questions on methodology, detailed underlying reasoning, or sources, contact contact@convoke.bio.
| Condition | Rank | Burden | Efficacy | Safety | Convenience | Pipeline |
|---|
