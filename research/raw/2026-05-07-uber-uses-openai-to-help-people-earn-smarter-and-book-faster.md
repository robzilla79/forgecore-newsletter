# Uber uses OpenAI to help people earn smarter and book faster

- Source: OpenAI News
- Published: Wed, 06 May 2026 00:00:00 GMT
- URL: https://openai.com/index/uber
- Domain: openai.com
- Tags: ai-tools, automation

## Feed summary

Uber uses OpenAI to power AI assistants and voice features that help drivers earn smarter and riders book faster across a global real-time marketplace.

## Extracted article text

Uber uses OpenAI to help people earn smarter and book faster
Uber uses OpenAI to power AI assistants and voice features that help drivers earn smarter and riders book faster across a global real-time marketplace.
Every day, millions of people rely on Uber to book rides, order meals, send packages, and earn flexibly. Behind every tap is a complex real-time marketplace shaped by traffic, weather, airport arrivals, local events, and demand. Uber operates at massive scale: 40 million trips per day, 10 million drivers and couriers across 15,000 cities in over 70 countries. Each city has its own operating dynamics, regulations, and rider behavior, creating a system that must adapt continuously at global scale.
Uber has long used machine learning to support its marketplace. And now, with the benefit of large language models and OpenAI frontier models, Uber can reason across complex signals more quickly, deliver fast conversational responses, and power voice experiences inside the app.
The collaboration between Uber and OpenAI is helping Uber build AI-powered products that simplify earning opportunities for drivers and couriers and reduce friction for riders. And using OpenAI’s models, Uber can ship streamlined products and experiences faster than ever.
“For the first time, technology is leading what can be solved. Problems that once felt out of reach are now possible to address.”
For drivers, flexibility is one of Uber’s biggest strengths. Some drive full-time, others just on weekends, while some drive between classes or shifts. This flexibility also means drivers are constantly evaluating options and asking questions: Where should I position myself right now? Is the airport worth driving to? Should I switch from rides to deliveries during lunch? Why did my earnings look different today?
To help answer those questions, Uber developed Uber Assistant, an AI-powered assistant designed to help drivers throughout their lifecycle on the platform—from onboarding and first trips to day-to-day earnings optimization.
“We want to enable drivers to make better decisions for themselves by providing a summarized view of the marketplace and real-time insights,” says Dharmin Parikh, Director of Product Management at Uber.
The Assistant helps drivers where and when to earn by turning complex data like earnings trends and heatmaps into simple, actionable positioning insights. They can then ask follow-up questions in plain language and receive tailored responses and easily navigate the app.
Uber’s goal is to reduce cognitive overhead—the effort required to interpret complex marketplace data while trying to earn.
That has proven especially valuable for new drivers. Uber found that using AI to summarize and easily communicate Uber’s real-world data can accelerate ramp-up by helping drivers learn workflows and marketplace dynamics much faster than through trial and error alone.
While Uber Assistant was initially expected to help newer drivers most, experienced drivers also returned repeatedly to ask follow-up questions and optimize their time on the platform—validating the product as a long-term utility, not just an onboarding tool.
“The Assistant is helping drivers ramp up quickly, compared to taking several hundreds of trips to understand how the platform works,” says Parikh.
For Uber, accuracy, safety, trustworthiness, and speed are top priorities when implementing any AI system whose outputs will interact with drivers and couriers. Critical considerations include responses staying within policy, and latency meeting the standard users expect from a real-time mobile app.
That’s why Uber designed Uber Assistant around three core principles: safety, trust, and low latency.
Uber’s engineering teams built a multi-agent architecture that routes each user request to the most appropriate specialized system. For example, earnings questions can be handled differently than onboarding questions, and marketplace guidance requires different reasoning than transactional actions.
This architecture enables Uber to route each task to the model best suited to its specific operational needs, ensuring that each query is handled with the appropriate focus on what matters most.
For lightweight classification and fast responses, Uber uses faster, nano/mini models. For more complex tasks, Uber leverages larger, reasoning models.
Uber also developed AI Guard, an internal governance layer that helps screen prompts and responses to promote safety, privacy, and security, enforce policies, reduce hallucinations, and maintain consistency across experiences.
When drivers receive accurate, useful recommendations, they come back. They ask more questions. They engage repeatedly. And they spend more productive time on the platform.
“If users don’t trust the system, you lose them quickly,” says Parikh. “But when they see value, they return.”
Uber is also applying OpenAI Realtime APIs to one of the next major interface shifts in technology: voice.
Typing into an app can be efficient for simple requests. But many transportation and commerce needs are more complex.
A traveler might want to say, “I have five pieces of luggage and five other people with me. I need a nice ride to the airport. What do you recommend?” An older adult or visually impaired rider may prefer speaking over tapping through menus.
Uber’s new voice experiences are designed to make those moments frictionless. Users can tap the microphone icon on the ‘where to’ search bar in the Uber app and request a ride using natural speech. The system uses Realtime API and other frontier models to interpret intent, leverages saved locations and customer context, and makes recommendations—while synchronizing spoken and visual responses inside the app.
That could mean suggesting UberXL for luggage-heavy trips or recognizing saved destinations like “home”.
“Voice removes the barrier of completing one task at a time,” says Parikh. “You can express full intent naturally, and the system can orchestrate the outcome.”
Voice also expands accessibility and unlocks new workflows across Uber’s ecosystem. On the driver side, it lets drivers interact with the app hands free. On the rider side, it can reduce friction for customers who want faster, simpler interactions.
“Voice removes the multi-tap barrier because you can say multiple things,” says Vidyasagar. “It unlocks that ability to connect the various parts of the ecosystem.”
As LLM capabilities evolve rapidly, Uber has also changed how teams build.
Engineers across the organization work with prompting, retrieval systems, evaluation pipelines, and orchestration frameworks. Product, legal, operations, and design teams collaborate more closely to define policy boundaries, test outputs, and improve user experiences.
Instead of a small centralized AI team owning innovation, intelligence can now be embedded throughout the company.
“It’s no longer one specialized group doing all of this,” says Vidyasagar. “Many teams can contribute because the
