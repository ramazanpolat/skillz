---
name: step-back
description: Reframe a stuck problem by separating the intended outcome from the current method, challenging unsupported assumptions, and finding simpler feasible alternatives. Use when the user says "take a step back", "what are we doing wrong", "take a deep breath", "out of the box", or asks to rethink a repeatedly failing approach. Do not trigger for literal breathing guidance or routine troubleshooting that is making progress.
---

# Step Back

Pause repeated attempts and reassess the problem framing. Treat “take a deep breath” as a signal to reconsider the approach; do not role-play breathing. Respond in the user's language.

## Separate the goal from the method

Extract the intended outcome, success criteria, attempted approaches, and observed failures from the available context. Express the outcome in one sentence, avoiding the name of the current tool or solution where possible. If the user explicitly requires a particular tool or product, do not silently remove it from scope.

Answer the question behind “How do we make X work?”: “What need will X meet once it works?” Do not invent missing information; ask only for information necessary to make the decision and unavailable in the existing context.

## Find the assumption keeping us stuck

Distinguish verified facts, actual constraints, and untested assumptions. Identify the assumption that makes the current approach appear necessary, and question the evidence supporting it. Do not confuse symptoms with causes; use previous failures as new evidence.

Use whichever of these questions help:

- Is this task actually necessary? Can we eliminate the step that creates the need?
- What changes if we change the tool, representation, order of operations, or layer at which we solve the problem?
- Can we remove a component instead of adding one?
- Could an existing capability, an off-the-shelf solution, or a manual process at an appropriate scale suffice?
- If we started from scratch today, disregarding the effort already spent, what would we choose?

## Compare genuinely different approaches

Where useful, develop two or three distinct approaches. Do not present configuration changes to the same method as different approaches. For each option, identify the assumption it changes, how it meets the goal, and its main cost or tradeoff. Keep the current approach as a baseline; do not reject it merely for the sake of novelty.

Do not manufacture simplicity by relaxing the user's explicit requirements, correctness criteria, or access boundaries. If an option requires changing a requirement, state that condition explicitly. Assess simplicity by the total implementation and operating burden; do not confuse moving work elsewhere with eliminating it.

Do not guarantee that a clever shortcut exists. Evaluate candidates against real operating conditions and situations in which they could fail. Use analogies to generate ideas, not as proof of feasibility. Where necessary, verify the decisive claim using available sources or tools.

## Move to the smallest test

Choose the strongest candidate and identify the cheapest reversible experiment that could disprove it. State the expected observation and the result that would rule out the approach. Run the experiment when appropriate within the authorized task; if the user requested only an assessment, provide the recommendation.

Do not repeat the same failed attempt without new evidence. After one round of reassessment, proceed with an actionable step or identify the specific missing information blocking the decision. If the current approach remains the best option, explain why; do not invent alternatives or a definitive diagnosis.

## Response

Provide a concise decision summary: the actual goal, the likely blocking assumption and its evidence, better candidates, the recommended approach, and the first test. State uncertainty explicitly. Do not produce an internal thought transcript, a long questionnaire, or generic motivational advice.
