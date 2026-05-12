# What is MCP (Model Context Protocol)?

- Source: Zapier Blog
- Published: Tue, 12 May 2026 04:00:00 GMT
- URL: https://zapier.com/blog/mcp
- Domain: zapier.com
- Tags: automation, workflows, operators

## Feed summary

Generative AI tools are impressive, but I've long argued that they aren't very useful in the real world unless they have access to more information than just their training data—and can actually do something with it. It's this ability that allows AI tools to create usable content, offer useful insights, and perform actions that actually move work forward.  Model Context Protocol (MCP) is a method of giving AI models the context they need and allowing them to take real action in other apps. So le

## Extracted article text

Generative AI tools are impressive, but I've long argued that they aren't very useful in the real world unless they have access to more information than just their training data—and can actually do something with it. It's this ability that allows AI tools to create usable content, offer useful insights, and perform actions that actually move work forward.
Model Context Protocol (MCP) is a method of giving AI models the context they need and allowing them to take real action in other apps.
So let's look more at what MCP is, how it works, and why it matters.
Table of contents:
What is MCP?
MCP is a two-way communication bridge between AI assistants and external tools, providing access to information, but more importantly, giving the AI the ability to take action. It was originally developed by Anthropic, but it's been embraced by just about every AI platform at this point.
It's an open source protocol designed to safely and securely connect AI tools to data sources like your company's CRM, Slack workspace, or dev server. That means your AI assistant can pull in relevant data and trigger actions in those tools—like updating a record, sending a message, or kicking off a deployment. By giving AI assistants the power to both understand and act, MCP enables more useful, context-aware, and proactive AI experiences.
Let's look at an example. If you connect ChatGPT to Slack's MCP server, you can tell ChatGPT to search your Slack for something and use that information to answer you. You could even tell ChatGPT to send a message in Slack on your behalf. All without ever leaving the ChatGPT interface. And you don't have to wire up a bunch of individual MCP servers because Zapier MCP lets you connect to 9,000+ apps with one connection.
How does MCP work?
MCP is a standard framework that defines how AI systems can interact with external tools, services, and data sources. Instead of having to create custom integrations for every service, MCP defines the basics of how they should interoperate, how requests are structured, what features are available, and how they can be discovered. It enables developers to easily and reliably build secure, two-way connections between AI tools and external data sources, apps, and other services.
People like to compare it to USB-C—a single cord that can connect to your phone, laptop, iPad, and even the fancy new immersion blender you got.
Another analogy is the World Wide Web. The hypertext transfer protocol (HTTP) defines how browsers and apps interact with websites and web servers. You can connect to zapier.com using Chrome, Safari, or even your Terminal app because they all use HTTP. MCP is an attempt to build an HTTP-like protocol for AI interoperability—it gives AI tools a common protocol to use.
Of course, that doesn't quite capture the whole picture because AI tools aren't actually like web browsers. They're able to understand language and intent, so MCP is designed to provide AI models with a structured set of options they can choose from. If you have an MCP server that's capable of downloading webpages from the internet, the AI model should be able to invoke it whether you say "go to zapier.com," "take me to zapier.com," or anything else like that. And if you say "get me my dog photos," it should know to invoke Google Drive instead.
MCP's client-host-server model
Now, let's look at more of the nitty-gritty. MCP operates using a client-host-server model:
The MCP host—typically, a chatbot, IDE, or other AI tool—is the central coordinator within the application. This is ChatGPT, Claude, Cursor, or whatever other AI tool you're spending your time in. Depending on how things are set up, the host may decide to call for something over MCP based on your request or based on an automated process.
The MCP client is initiated by the host and connects to a single server; it handles communications between the host and the server.
The MCP server connects to a data source or tool, either local or remote, and exposes specific capabilities. For example, an MCP server connected to a file storage app can provide capabilities like "search for a file" and "read a file," while an MCP server connected to your team chat app can provide capabilities like "get my latest mentions" and "update my status." Most business apps have MCP servers at this point (or if you're a developer, you can write your own).
MCP servers can provide data using three basic methods:
Prompts are pre-defined templates for the LLM that can be selected by the user through slash commands, menu options, and the like.
Resources are structured data, like files, data from a database, or a commit history, that provide additional context to the LLM.
Tools are functions that allow the model to take action, like interacting with an API or writing something to a file.
While MCP might sound superficially similar to how APIs operate, the two differ significantly in design, intent, and flexibility. An API offers a direct, service-specific interface, while MCP is designed to be a unified framework. Many MCP servers use APIs when they're triggered over MCP, so the two often work in tandem—but they're not the same thing.
What problem is MCP solving?
AI tools are only as useful as the data they have access to and the actions they can take.
For general queries, an LLM's training data or web search will be sufficient. But if you want an AI tool like ChatGPT or Claude to know how your company's sales figures compare to last quarter, how your competitor's marketing has changed in response to market conditions, or simply what your CEO's email address is, then you need some way to provide it with the relevant information.
And if you want the AI to do something with that information—like send a report, create a task in your project management tool, update a record in your CRM, or notify your team on Slack—you need a way for it to interact with those apps. MCP makes that easier by giving AI tools a standardized way to discover and invoke actions in external systems. It bridges the gap between understanding and execution, so the AI isn't just responding with insights—it's actively getting things done.
For example, with Zapier's MCP implementation, you can trigger actions directly within all your work apps from your favorite chatbot or AI coding agent. That means your AI tools aren't limited to answering questions—they can take action, like sending an email, creating a task, or updating a record. You'll never leave your chatbot or agent, but work will still happen in your other apps.
Previously, this would mean building a custom integration for every app you wanted to get insights from or take action in. Instead, MCP offers a standardized blueprint for how AI tools can interact with any data source. Any app that supports MCP is able to offer a structured set of tools or actions that an AI assistant or agent can leverage. When you ask an AI to do something, it can check what tools are available to it and take the appropriate a
