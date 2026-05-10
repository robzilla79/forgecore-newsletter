# Advancing voice intelligence with new models in the API

- Source: OpenAI News
- Published: Thu, 07 May 2026 10:00:00 GMT
- URL: https://openai.com/index/advancing-voice-intelligence-with-new-models-in-the-api
- Domain: openai.com
- Tags: ai-tools, automation

## Feed summary

Explore new realtime voice models in the OpenAI API that can reason, translate, and transcribe speech, enabling more natural and intelligent voice experiences.

## Extracted article text

We’re introducing three audio models in the API that unlock a new class of voice apps for developers. With these models, developers can build voice experiences that feel more natural, respond more intelligently, and take action in real time:
- GPT‑Realtime‑2, our first voice model with GPT‑5‑class reasoning that can handle harder requests and carry the conversation forward naturally.
- GPT‑Realtime‑Translate, a new live translation model that translates speech from 70+ input languages into 13 output languages while keeping pace with the speaker.
- GPT‑Realtime‑Whisper, a new streaming speech-to-text that transcribes speech live as the speaker talks.
Try GPT-Realtime-2
What can I ask?
After you start the session, try saying one of these:
- I’m hosting a last-minute dinner tonight. I have 30 minutes, two vegetarian friends, one mushroom-hater, and a tiny kitchen. Help me plan a simple menu.
- I’m welcoming guests to a live event in Japan. Say a warm, natural welcome in Japanese — like a host kicking off something special.
- My order number is Orbit-742Q. Repeat it back clearly so I can confirm it’s right.
- Help me practice telling my team we hit our launch milestone. First say it with quiet confidence, then with more excitement.
- I’m planning trivia for a road trip. Give me three trick questions that sound deceivingly simple, then explain each answer in one sentence.
Voice is becoming one of the most natural ways for people to use software. It lets someone ask for help while driving, change a travel plan while walking through an airport, get support in their preferred language, or move through a task without stopping to type.
But building useful voice products takes more than fast turn-taking or a natural-sounding voice. A voice agent needs to understand what someone means, keep track of context, recover when a request changes, use tools while the conversation continues, and respond in a way that feels appropriate to the moment.
Together, the models we are launching move realtime audio from simple call-and-response toward voice interfaces that can actually do work: listen, reason, translate, transcribe, and take action as a conversation unfolds.
As voice becomes a more natural way to use software, we’re seeing developers build around three emerging patterns in voice AI:
- Voice-to-action, where people can describe what they need and the system can reason through the request, use tools, and complete the task. For example, Zillow is building an assistant that can listen, reason, and act on requests like: “find me homes within my BuyAbility, avoid busy streets, and schedule a tour for Saturday.”
- Systems-to-voice, where software can turn context into live spoken guidance. For example, a travel app could proactively tell a traveler: “Your inbound flight is delayed, but you can still make your connection. I found the new gate, mapped the fastest route through the terminal, and your bag is still expected to transfer.”
- Voice-to-voice, where AI can help live conversations continue across languages, tasks, or changing context. For example, Deutsche Telekom is building voice support experiences where customers can speak in the language they’re most comfortable using, while the model translates the conversation in real time.
These patterns can also work together. Priceline is working toward a future where travelers can manage entire trips by voice: searching for flights and hotels conversationally, handling changes like adjusting a hotel reservation after a flight delay or getting real-time updates on TSA wait times, and translating conversations once travelers are on the ground.
GPT‑Realtime‑2 is built for live voice interactions where the model keeps the conversation moving while it reasons through a request, calls tools, handles corrections or interruptions, and responds in a way that fits the moment.
- Preambles: Developers can enable short phrases before a main response, like “let me check that” or “one moment while I look into it,” so users know the agent is working on the request.
- Parallel tool calls and tool transparency: The model can call multiple tools at once and make those actions audible with phrases like “checking your calendar” or “looking that up now,” helping agents stay responsive while completing tasks.
- Stronger recovery behavior: The model can recover more gracefully by saying things like “I’m having trouble with that right now,” instead of failing silently or breaking the conversation.
- Longer context for agentic workflows: We’re increasing the context window from 32K to 128K to support longer, more coherent sessions and more complex task flows.
- Stronger domain understanding: The model better retains specialized terminology, proper nouns, healthcare terms, and other vocabulary that matters in production settings.
- More controllable tone and delivery: The model can better adjust its tone—speaking calmly while resolving an issue, empathetically when a user is frustrated, or upbeat when confirming a successful action.
- Adjustable reasoning effort: Developers can now select from minimal, low, medium, high, and xhigh reasoning levels, with low as the default, balancing lower latency for straightforward interactions with more deliberate reasoning for complex requests.
The gains show up on audio evals that map closely to production voice agents: GPT‑Realtime‑2 (high) scores 15.2% higher on Big Bench Audio for audio intelligence than GPT‑Realtime‑1.5. GPT‑Realtime‑2 (xhigh) scores 13.8% higher on Audio MultiChallenge for instruction following, improving over GPT‑Realtime‑1.5 and showing stronger reasoning, context management, and control in live conversations.
The magic of GPT‑Realtime‑2 shows up across a variety of different use cases:
During early testing, businesses used GPT‑Realtime‑2 to build voice agents that help customers and employees get things done through natural conversation:
“What stood out about GPT-Realtime-2 was the intelligence and tool-calling reliability it brings to complex voice interactions. On our hardest adversarial benchmark, this translates to a 26-point lift in call success rate after prompt optimization (95% vs. 69%). GPT-Realtime-2 is also materially more robust on Fair Housing compliance, which is critical for our business. The combination of agentic competence and guardrail strength is what makes it viable for production voice at Zillow.”
GPT‑Realtime‑Translate helps developers build live multilingual voice experiences where each person can speak in their preferred language and hear the conversation translated in real time and read the real time transcriptions. It supports more than 70 input languages and 13 output languages, making it useful for customer support, cross-border sales, education, events, media, and creator platforms serving global audiences.
For developers, live translation needs to preserve meaning while keeping pace with the speaker, even when people speak naturally, switch context, or use regional pronun
