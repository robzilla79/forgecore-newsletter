# Revisiting “No Silver Bullets” in the age of AI

- Source: The Pragmatic Engineer
- Published: Tue, 12 May 2026 17:10:28 GMT
- URL: https://newsletter.pragmaticengineer.com/p/revisiting-no-silver-bullets-in-the
- Domain: newsletter.pragmaticengineer.com
- Tags: engineering, builders, operators

## Feed summary

Does the noted &#8220;No Silver Bullets&#8221; paper by the author of a classic engineering book still hold up, 40 years later? Is AI the long-sought single silver bullet &#8211; or has one been around for years?

## Extracted article text

Revisiting “No Silver Bullets” in the age of AI
Does the noted “No Silver Bullets” paper by the author of a classic engineering book still hold up, 40 years later? Is AI the long-sought single silver bullet – or has one been around for years?
Before we start, some news: my tech compensation site focused on tech total compensation (TC) in Europe, TechPays has been acquired by Levels.fyi! TechPays was a project I’ve been building on the side with engineering manager Zsombor Erdődy-Nagy for a few years, and both of us are pleased that the site found a new and welcoming home. Read more.
Four decades ago, the writer of ‘The Mythical Man-Month’ (1975), drew on folklore about werewolves to publish a paper about the prospects of a so-called silver bullet for software development that would make professionals much more productive at their craft.
Frederick P. Brooks published “No Silver Bullet – Essence and Accident in Software Engineering” in 1986, and as the title suggests, it is pessimistic about the existence of any silver bullets. The term refers to a super weapon capable of dropping otherwise near-unstoppable werewolves and other creepy supernatural beings in European folk tales.
Since its release, this paper might have become even better-known than Mythical Man-Month (MMM). In 1995, the second edition of that book included Brooks’ later essay as chapter 17, along with an additional chapter of reflections.
In this article, we look into whether the essay was correct in its disbelief in silver bullets, or whether any did indeed slay the beast of unproductivity for developers over the course of time. Also, how does AI agents generating so much code, as of today, challenge the entire premise – or not?
We cover:
“No silver bullets” – why has it held up? No single new technology or methodological breakthrough by itself introduced magnitudes-of-improvement to the areas that really matter in software engineering. Is that unusual?
Is SRE a silver bullet? Google’s Search team introduced the SRE discipline, and won orders-of-magnitude superior reliability to its competitors. But why only Google Search?
Was open source + GitHub a silent silver bullet? No development had a bigger impact on the wider tech industry than the open source wave since the 2010s. Has it been a silent silver bullet, an overlooked cause?
Could AI be a silver bullet? At first glance, AI generates 100x-or-more code output. But productivity, reliability, and simplicity improvements are a bit unimpressive – at least for now.
Brooks was a computer scientist who led IBM’s System/360 and OS/360 operating systems development, ‘The Mythical Man-Month’ was published in 1975. Last year, we did a deepdive into this engineering classic (Part 1, Part 2, Part 3, Part 4), delving into its predictions and legacy.
1. No silver bullets?
The paper delves into folklore for its motif, a ‘silver bullet,’ and uses it to pose the question of whether there would be any “silver bullets” on the horizon (in 1986) that could be similarly fatal to software engineering complexity. From the paper (emphasis mine:)
“Of all the monsters who fill the nightmares of our folklore, none terrify more than werewolves, because they transform unexpectedly from the familiar into horrors. For these, one seeks bullets of silver that can magically lay them to rest.
The familiar software project has something of this character (at least as seen by the non-technical manager), usually innocent and straightforward, but capable of becoming a monster of missed schedules, blown budgets, and flawed products. So, we hear desperate cries for a silver bullet, something to make software costs drop as rapidly as computer hardware costs do.
But, as we look to the horizon of a decade hence, we see no silver bullet. There is no single development, in either technology or management technique, which by itself promises even one order of magnitude improvement in productivity, in reliability, in simplicity.
Skepticism is not pessimism, however. Although we see no startling breakthroughs, and indeed, believe such to be inconsistent with the nature of software, many encouraging innovations are under way. A disciplined, consistent effort to develop, propagate, and exploit them should indeed yield an order-of-magnitude improvement. There is no royal road, but there is a road.
The first step toward the management of disease was replacement of demon theories and humor theories by the germ theory. That very step, the beginning of hope, in itself dashed all hopes of magical solutions. It told workers that progress would be made stepwise, at great effort, and that a persistent, unremitting care would have to be paid to a discipline of cleanliness. So it is with software engineering today.”
In 1995, Brooks revisited his idea that silver bullets weren’t real in the software domain. From the Mythical Man-Month’s anniversary edition:
“No Silver Bullet” asserts and argues that no single software engineering development will produce an order-of-magnitude improvement in programming productivity within ten years (from the paper’s publication in 1986). We are now nine years into that decade, so it is timely to see how this prediction is holding up.
Whereas The Mythical Man-Month generated many citations but little argument, “No Silver Bullet” has occasioned rebuttal papers, letters to journal editors, and letters and essays that continue to this day.
Most of these attack the central argument that there is no magical solution, and my clear opinion that there cannot be one. Most agree with most of the arguments in “NSB,” but then go on to assert that there is indeed a silver bullet for the software beast, which the author has invented. As I reread the early responses today, I can’t help noticing that the nostrums pushed so vigorously in 1986 and 1987 have not had the dramatic effects claimed.”
Brooks re-concluded that there had been no technological breakthroughs of the type postulated in NSB.
But motivation can also have silver bullet-like effects and always has had, he found via more research into scientific evidence that motivation can boost productivity. In his own words:
“Since “NSB,” Bruce Blum has drawn my attention to the 1959 work of Herzberg, Mausner, and Sayderman.
They find that motivational factors can increase productivity. On the other hand, environmental and accidental factors, no matter how positive, cannot; but these factors can decrease productivity when negative. “NSB” argues that much software progress has been the removal of such negative factors: stunningly awkward machine languages, batch processing with long turnaround times, poor tools, and severe memory constraints.”
Today, it’s a long time since the mid-nineties; with the benefit of hindsight, were there any silver bullets flying between then and 2022, which fit the bill as slayers of unproductiveness? I suggest a few, below. If you can name other silver bullets since the launch of Windows 95, please do so in the comment
