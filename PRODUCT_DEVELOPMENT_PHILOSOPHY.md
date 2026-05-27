# Product Development Philosophy

These principles guide every feature decision in this codebase.
Read before designing any new feature or proposing a schema change.

## 1. Data must be migratable
Schema evolves. Raw inputs, files, relationships, decisions, and change history must survive across migrations.

## 2. Intake burden should be minimized
Don't ask users to fill many rigid fields before useful information is captured.

## 3. Display and reminders should be richer than intake
Ask less. Show more — structure, reminders, history, missing pieces, options, decisions.

## 4. LLM carries interpretation work
AI classifies, summarizes, detects updates, identifies tradeoffs, proposes field changes, asks clarifying questions. **AI proposes; user confirms.**

## 5. Change Log is mandatory but not sufficient
Change Log records WHAT changed. Project Journal records WHY product thinking evolved.

## 6. Projects are evolving hypotheses, not static forms
A project changes through factory conversations, cost discoveries, material constraints, packaging ideas, market positioning. Don't lock too early.

## 7. Support options and scenarios
Don't force one project into one fixed cost / material / brand / SKU before the team has explored alternatives.

## 8. User mental flow drives iteration
Users think in discoveries, tradeoffs, decisions, options, and questions — not database fields. Design UI around those mental moves.

## 9. Preserve raw inputs forever
Original text / files / images / business plans remain available so future schema changes can re-parse old information.

## 10. Manual forms are fallback
The long-term ideal is unified intake: user provides text/file/image, system classifies, user confirms, system routes correctly. Manual forms exist when AI fails or for power-user precision.
