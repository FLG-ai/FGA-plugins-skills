# Recap templates

Two files per course. The user reads these instead of rewatching, so they have to
stand on their own, read easily and stay practical. Write them for a busy
business owner who isn't technical: plain everyday words, short sentences, "you".
If a tech term can't be avoided, explain it in a few words the first time it
appears ("a skill, the small instruction file you upload to Claude"). Keep the
teacher's real examples, numbers and names, because those make it stick. Leave
out the filler: no housekeeping, no "drop it in the chat", no sponsor plugs,
no step-by-step clicking that the notes PDF already covers.

Source of truth, in this order: the transcript, then the lesson notes and
attachments, then the skill files themselves (read each SKILL.md so "what it
does" is what it actually does). Never add anything the lesson didn't say. If a
lesson has no transcript, write from the notes and say so in the Source line.

Every recap follows these writing rules: no em dashes, no semicolons, none of
the banned words, and a read-through for anything that sounds machine-written before it's saved.

---

## Lesson recap: `_recaps/<lesson stem> - Recap.md`

About 250 to 450 words. A 2-hour live session or a big prompt pack can run to 650, never more.

```markdown
# <Lesson title>, recap

**In one line:** what this lesson gets you, in plain words.

## What it covers
- 3 to 6 bullets, each one an actual point the teacher made, with the example
  or number they used. Most important first.

## Do this
1. The practical steps to put it to work this week, in order. 2 to 5 steps.

## Skills and tools from this lesson
Only if the lesson gave or used any. One short block per skill, prompt or tool:

**<Name>** (skill / prompt / tool, and where the file is if we saved it)
- What it does: one sentence.
- When to use it: the moment in your week it's for.
- How: 1 to 3 plain steps.
- Why bother: the payoff, in time or money or results if the teacher gave one.

## Worth remembering
- 1 to 3 rules of thumb or lines worth keeping, quoted short with who said it.

**Source:** video, transcript, notes (relative links). Add "written from the notes
only, no transcript" when that's the case.
```

---

## Course recap: `COURSE RECAP.md` at the course root

Built from the lesson recaps once they're all written, so it adds no new claims.
About 600 to 1,000 words for a typical course.

```markdown
# <Course>, course recap

**What this course is for:** 2 to 3 sentences on the outcome it promises and
who it's for.

## The big ideas
- 5 to 8 bullets, the points that come up again and again or matter most.

## The method, lesson by lesson
1. **<Lesson 1>**: one line on what it teaches. [Recap](<_recaps/...>)
2. ... every lesson, lesson 1 first.

## Every skill and tool in one place
| Skill or tool | What it does | When to use it | From |
|---|---|---|---|
One row each, linking the saved .skill or file where there is one.

## Start with these three
1. The three highest-value moves from the whole course, practical and in order.

## Still to come
Only for a live course: sessions not released yet, so a re-run knows to update this.
```
