# Scaling Trusted Access for Cyber with GPT-5.5 and GPT-5.5-Cyber

- Source: OpenAI News
- Published: Thu, 07 May 2026 13:00:00 GMT
- URL: https://openai.com/index/gpt-5-5-with-trusted-access-for-cyber
- Domain: openai.com
- Tags: ai-tools, automation

## Feed summary

OpenAI expands Trusted Access for Cyber with GPT-5.5 and GPT-5.5-Cyber, helping verified defenders accelerate vulnerability research and protect critical infrastructure.

## Extracted article text

Scaling Trusted Access for Cyber with GPT‑5.5 and GPT‑5.5‑Cyber
How our latest models help each layer of the defensive ecosystem and accelerate the security flywheel.
For years we’ve been chronicling our work to accelerate cybersecurity defenders, as part of our broader work to build the core infrastructure for AI. Last week, we released our action plan Cybersecurity in the Intelligence Age, which lays out our vision for democratizing AI-powered defense. Two weeks ago, we released GPT‑5.5, our smartest and most intuitive model to date, which is already delivering powerful cybersecurity capabilities to developers and security teams through Trusted Access for Cyber (TAC).
Today, we are rolling out GPT‑5.5‑Cyber in limited preview to defenders responsible for securing critical infrastructure to support specialized cybersecurity workflows that help protect the broader ecosystem.
We are focused on providing proportional safeguards and access to empower cyber defenders to protect society, and our approach has been informed by conversations with cybersecurity and national security leaders across federal and state government and major commercial entities.
The cyber defense ecosystem is broad, and GPT‑5.5 and GPT‑5.5‑Cyber play different roles in meeting the needs of organizations and researchers across it, depending on the task, the setting, and the safeguards around how the model is used. For most teams, GPT‑5.5 with TAC is our strongest broadly useful model for legitimate defensive work, with strong safeguards against misuse.
In this post, we are sharing more details on how Trusted Access for Cyber works, how GPT‑5.5 and GPT‑5.5‑Cyber meet the varied needs of defenders across the ecosystem, and how different levels of access affect model outputs.
Trusted Access for Cyber is an identity and trust-based framework designed to help ensure enhanced cyber capabilities are being placed in the right hands. It is designed to make the cyber capabilities of GPT‑5.5 more useful for verified defenders working on defensive tasks, while continuing to restrict requests that could enable real-world harm.
When defenders are vetted and approved for Trusted Access for Cyber, they receive lower classifier-based refusals to enable authorized cybersecurity workflows, including vulnerability identification and triage, malware analysis, binary reverse engineering, detection engineering, and patch validation. Safeguards continue to block malicious activity such as credential theft, stealth, persistence, malware deployment, or exploitation of third-party systems.
As we announced last week, with increased access, defenders are required to have phishing-resistant account security protections. Individual members of Trusted Access for Cyber accessing our most cyber capable and permissive models will be required to enable Advanced Account Security beginning June 1, 2026. Organizations with trusted access can, as an alternative, attest that they have phishing resistant authentication as part of their single sign-on workflow.
Here is a breakdown for how to think about the current trusted access levels:
Access | What changes | Intended use cases |
GPT-5.5 (default) | Standard safeguards for general-purpose use | General-purpose, developer, and knowledge work |
GPT-5.5 with TAC | More precise safeguards for verified defensive work in authorized environments | Most defensive security workflows, including secure code review, vulnerability triage, malware analysis, detection engineering, and patch validation |
GPT-5.5-Cyber | Most permissive behavior for specialized authorized workflows, paired with stronger verification and account-level controls | Preview access for specialized workflows, including authorized red teaming, penetration testing, and controlled validation |
The differences between model access levels are most pronounced when comparing prompts and responses. The first example illustrates how GPT‑5.5 compares to GPT‑5.5 with Trusted Access for Cyber on a defensive task: create a proof-of-concept from a published vulnerability to validate remediation within an authorized environment.
For most defenders, GPT‑5.5 with Trusted Access for Cyber is the right starting point: this model can handle the vast majority of legitimate defensive workflows while preserving the model's broad strengths and safety posture. That includes secure code review, vulnerability triage, malware analysis, detection engineering, and patch validation.
More specialized access becomes relevant only when authorized workflows still run into refusals. This occurs with higher risk workflows such as red teaming and penetration testing, where defenders may need to go beyond analysis, and validate exploitability in a controlled environment. GPT‑5.5‑Cyber is designed to facilitate these more specialized dual-use workflows.
Here’s a simple example that shows what that looks like in practice:
GPT‑5.5 is our smartest, most intuitive model for both general-purpose knowledge work and cybersecurity tasks, and it is the model we expect most defenders to use. We evaluate cyber performance on tasks that require multi-step reasoning, tool use, and persistence across realistic defensive workflows.
The initial preview of cyber-permissive models like GPT‑5.5‑Cyber is not intended to significantly increase cyber capability beyond GPT‑5.5 - it’s primarily trained to be more permissive on security-related tasks.
As a result, this first preview is not expected to outperform GPT‑5.5 across every cyber evaluation. Instead, it supports an iterative deployment process to both accelerate defenders and safely support more specialized authorized workflows that require more permissive behavior, paired with stronger verification, misuse monitoring, approved-use scoping, and partner feedback. For now, GPT‑5.5 with Trusted Access for Cyber remains the recommended starting point for most security workflows.
We are partnering with security vendors because they sit where model capability can become customer protection: discovery, development, detection, response, and network enforcement. When those layers improve together, they create a security flywheel: researchers disclose vulnerabilities with exploit proof-of-concepts and patch guidance, software supply chain tools prevent vulnerable code and compromised dependencies from reaching production, EDR and SIEM partners detect exploitation in the wild, and network and security providers deploy WAF-level mitigations while fixes roll out.
GPT‑5.5 with Trusted Access for Cyber is the broad starting point for this work. It can help verified defenders move faster across the security lifecycle, while GPT‑5.5‑Cyber lets a smaller set of partners study advanced workflows where specialized access behavior may matter. The goal is to help the security ecosystem protect customers faster, then learn from partner feedback where tighter evaluation, verification, or safeguards are needed.
Network and security providers
Network and securi
