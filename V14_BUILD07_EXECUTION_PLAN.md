# v1.4 Build 07 Execution Plan — Apply Sandbox To Project Plan

## Status

Execution plan for the seventh v1.4 Planning Sandbox implementation build.

Predecessor: v1.4 Build 06 — Canvas Interaction Hardening.

Successor: v1.4 Build 08 — Save Workflow As Template.

Canonical design reference: `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md`
§2 Migration 009, §12 Apply detailed semantics, §13 route/service table, and
`V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md` §Apply Semantics / §v1.4
Build 07.

## Revision Note — 2026-06-09 Claude Review Fold-In

Claude Code reviewed the first Build 07 plan and identified one real
data-integrity gap plus several safety clarifications. This revision folds in
the accepted guidance:

- `delayed` phases now block Apply as active execution.
- `skipped` phases are treated as untouched-and-replaceable only when they have
  no actual dates; they must still appear in the replacement warning.
- The phase deletion predicate is now explicit.
- New phase notes null-handling is locked.
- The Apply form's planned start date is named `apply_start_date` in service
  specs to avoid field-name ambiguity.
- Apply updates project stage/delay inside the same service transaction instead
  of relying on a second post-commit recalculation.
- Build 07 explicitly writes no `phase_plan_changes` rows.
- Tests must prove each active-execution precondition separately, viewer Apply
  affordances are hidden, and no AI Apply tool is registered.

One Claude caveat is stale for current repo state: v1.4 Builds 04, 05, and 06
are already implemented in this working tree, and the user explicitly resumed
sandbox work.

## Purpose

Build 07 creates the only bridge from the experimental Planning Sandbox into
the live project Timeline. A PM/admin can explicitly apply a valid draft
sandbox, replacing an untouched not-started phase plan with phases computed
from the sandbox graph.

This build must feel deliberate, audited, and reversible by policy review. It
must not silently overwrite active execution.

## Scope

In:

1. Add migration 009 for `planning_apply_events`.
2. Add `PlanningApplyEvent` SQLAlchemy model and relationship(s).
3. Add service helpers in `app/crud.py`:
   - `validate_sandbox_for_apply`
   - `get_sandbox_apply_preview`
   - `apply_sandbox_to_project`
4. Add POST route in `app/routes/projects.py`:
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/apply`
5. Add Apply confirmation UI to `planning_sandbox.html`:
   - visible only for PM/admin users on draft sandboxes,
   - disabled/blocked when hard validation or active-execution preconditions
     fail,
   - planned start date defaults to today,
   - computed end date updates client-side from total days,
   - launch-date update checkbox defaults off,
   - replacement warning lists existing phases that will be deleted.
6. Extend Timeline History derivation so apply events appear as a polished
   event in the existing History feed.
7. Add EN/zh i18n keys with exact parity.
8. Add `test_v14_build07.py`.

Out:

- No Save as Template.
- No AI tools.
- No multiple-draft sandbox support.
- No partial merge into active execution.
- No append-after-started-phases mode.
- No editing applied snapshots.
- No dependency types beyond `finish_to_start`.
- No project phase mutation before the explicit Apply POST.
- No `phase_plan_changes` rows; Apply creates a new phase plan rather than
  editing dates on existing phases.

## Architecture Review

1. Problem solved: PMs need to turn a trusted sandbox workflow into the actual
   project timeline without manually recreating every phase.
2. Tables affected: adds `planning_apply_events`; writes
   `planning_sandboxes`, `project_phases`, optional `projects.planned_launch_date`,
   and `project_changes`.
3. Real column vs notes: apply audit needs a queryable event table because
   Timeline History and future rollback/debug views need node count, dates, and
   snapshot JSON.
4. Service layer: route delegates all validation, deletion, phase creation,
   sandbox status update, apply event creation, and change-log write to
   `crud.apply_sandbox_to_project`.
5. Change log: Apply writes one `project_changes` row with
   `change_type='plan_applied'` and `source_type='planning_sandbox'`.
6. `source_type='planning_sandbox'` is allowed because `source_type` is a plain
   string column in the current schema, not an enum.
7. Rollback: migration is additive; disabling the route leaves applied
   snapshots and audit events readable. Existing phase-delete/create behavior is
   protected by preconditions and tested.

## Backend Honesty Mapping

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Apply button | draft sandbox + role permission + validation preview | `apply_sandbox_to_project` | hidden unless `can_edit_project` and sandbox is `draft`; disabled if blocked | PM/admin only | template + browser test |
| Node count | `planning_sandbox_nodes` | none directly | count current sandbox nodes | all authenticated view | preview/service test |
| Total estimated days | `compute_sandbox_schedule.total_days` | none directly | recomputed server-side on preview and confirm | all authenticated view | service + route test |
| Planned start date | modal form input | POST apply form | defaults to today; server parses ISO date | PM/admin only | route validation test |
| Computed end date | planned start + `total_days` | persisted in `planning_apply_events` | server recomputes; client preview is convenience only | all view after apply through history | service + browser test |
| Update launch date checkbox | modal form input | optional `Project.planned_launch_date` write | default off; only checked updates project launch date | PM/admin only | service route tests on/off |
| Replacement warning | existing `project_phases` rows | deletion happens only inside Apply | lists phases that pass untouched-plan preconditions | PM/admin only | browser/source test |
| Active execution refusal | existing `ProjectPhase` actual dates/status + active phase blockers | no write | refuse if any precondition fails | PM/admin sees reason | service + route test |
| Apply audit event | `planning_apply_events` | `apply_sandbox_to_project` | stores graph snapshot, node count, total days, start/end, counts | all project viewers can see history | model/migration/history test |
| Timeline History apply card | `planning_apply_events` + `project_changes` | apply service creates both | derived into existing event feed bucket | all project viewers | history/browser test |

## Locked Implementation Decisions

1. **Apply is the only live-plan mutation path.** Builds 01-06 remain
   sandbox-only. Build 07 mutates `project_phases` only inside
   `apply_sandbox_to_project`.
2. **No active execution overwrite.** Apply refuses if any existing phase has
   `actual_start_date`, `actual_end_date`, status `in_progress`/`done`, or an
   active phase-linked blocker.
3. **Delete + insert, not update.** When preconditions pass, all existing
   untouched phases are deleted and new phases are inserted from the sandbox
   topological order. `phases_updated=0`.
   Delete predicate is explicit:
   `project_id=? AND actual_start_date IS NULL AND actual_end_date IS NULL AND status IN ('not_started','skipped')`.
4. **Server recomputes everything on confirm.** Client modal values are
   advisory; schedule and validation are recomputed from DB rows in the service.
5. **Soft warnings do not block Apply.** Hard errors and active-execution
   preconditions block Apply. Soft warnings are shown and acknowledged by the
   act of confirming.
6. **Launch date update defaults off.** The project planned launch date changes
   only when the PM explicitly checks the modal toggle.
7. **Applied sandbox becomes read-only.** Successful Apply sets
   `planning_sandboxes.status='applied'` and preserves the graph as a readable
   snapshot.
8. **Audit is mandatory.** Successful Apply creates both a
   `planning_apply_events` row and a project change-log row.
9. **No silent AI behavior.** No AI tool can call Apply in this build.
10. **No phase plan change rows.** `phase_plan_changes` audits in-place date
    edits. Apply deletes untouched phases and creates a new plan, so the
    apply event + project change row are the correct audit records.

## Apply Transaction

`crud.apply_sandbox_to_project(db, project_id, sandbox_id, apply_start_date,
update_launch_date, user_id)` must:

1. Load the project and draft sandbox by `project_id`/`sandbox_id`.
2. Recompute `compute_sandbox_schedule(..., require_nodes=True)`.
3. Reject hard schedule errors.
4. Re-check active-execution preconditions.
5. Snapshot the sandbox graph and schedule payload.
6. Delete existing untouched phases for the project using:
   `actual_start_date IS NULL`, `actual_end_date IS NULL`, and
   `status IN ('not_started','skipped')`.
7. Create new `ProjectPhase` rows in schedule/topological order:
   - `phase_name = node.title`
   - `phase_type = node.phase_type`
   - `phase_order = 1..N`
   - `status = 'not_started'`
   - `planned_start_date = apply_start_date + node.computed_start_day`
   - `planned_end_date = apply_start_date + node.computed_end_day`
   - `owner = node.owner_role`
   - `notes = non-empty parts of [deliverable, exit_criteria] joined with " / ";
     if both are empty, notes stays NULL`
8. Optionally update `Project.planned_launch_date = computed_end_date`.
9. Mark sandbox applied (`status`, `applied_at`, `applied_by_user_id`,
   `last_computed_total_days`).
10. Insert `PlanningApplyEvent`.
11. Write project change summary with `change_type='plan_applied'`.
12. Recalculate `current_stage`, `estimated_launch_date`, and `updated_at`
    inside the same service transaction, then commit once.

## Active-Execution Preconditions

Apply refuses with `preconditions_failed` and a structured list if any are true:

| Code | Check |
|---|---|
| `phase_has_actual_start` | any existing phase has `actual_start_date` |
| `phase_has_actual_end` | any existing phase has `actual_end_date` |
| `phase_active_status` | any existing phase status is `in_progress`, `done`, or `delayed` |
| `active_blocker_attached` | any active `ProjectBlocker` has a non-null phase_id for this project |

`delayed` is treated as active execution for Apply purposes because a delayed
phase already reflects a live schedule condition. `skipped` is not active
execution by itself; skipped phases with no actual dates are replaceable, but
they must be shown in the replacement warning. Skipped phases with actual dates
are blocked by the actual-date preconditions.

## UX Behavior

- Sandbox header/toolbar shows **Apply to Timeline** for editable draft
  sandboxes.
- Clicking opens a compact confirmation modal/panel, not an immediate apply.
- Modal shows:
  - node count,
  - total estimated days,
  - planned start date,
  - computed end date,
  - update project launch date checkbox,
- replacement warning and current phase names,
    including skipped phase names when they will be replaced,
  - hard/precondition errors when blocked.
- Confirm submits the existing server form route.
- Success redirects to the project detail Timeline Command Center or sandbox
  snapshot with a visible success message.
- The applied sandbox page is read-only and clearly labeled as a snapshot.

## i18n Lock

Build 07 should add these keys unless implementation amends this plan before
coding:

| Key | EN intent | ZH intent |
|---|---|---|
| `sandbox.apply` | Apply to Timeline | 应用到时间线 |
| `sandbox.apply_confirm_title` | Apply sandbox to timeline | 将沙盒应用到时间线 |
| `sandbox.apply_confirm_body` | This will replace the current untouched phase plan. | 这会替换当前尚未执行的阶段计划。 |
| `sandbox.apply_node_count` | Nodes | 节点 |
| `sandbox.apply_total_days` | Estimated days | 预计天数 |
| `sandbox.apply_start_date` | Planned start date | 计划开始日期 |
| `sandbox.apply_end_date` | Computed end date | 计算结束日期 |
| `sandbox.apply_update_launch` | Update project launch date | 更新项目上市日期 |
| `sandbox.apply_replaces` | Existing phases to replace | 将被替换的现有阶段 |
| `sandbox.apply_no_existing_phases` | No existing phases will be replaced. | 没有现有阶段会被替换。 |
| `sandbox.apply_blocked` | Apply blocked | 无法应用 |
| `sandbox.apply_invalid_graph` | Fix hard errors before applying. | 请先修复硬性错误再应用。 |
| `sandbox.apply_active_execution` | Existing timeline has active execution. | 当前时间线已有执行记录。 |
| `sandbox.apply_success` | Sandbox applied to timeline. | 沙盒已应用到时间线。 |
| `sandbox.apply_error` | Could not apply sandbox. | 无法应用沙盒。 |
| `history.plan_applied` | Plan applied | 计划已应用 |

Current post-Build-06 count is 775 keys; this list would bring parity to
791/791.

## Test Plan

Run:

```bash
python3 test_v14_build07.py
python3 test_v14_build06.py
python3 test_v14_build05.py
python3 test_v14_build04.py
python3 test_build_v121.py
```

`test_v14_build07.py` must cover:

- Plan file exists and locks active-execution refusal, audit event, and explicit
  Apply.
- Migration 009 creates `planning_apply_events` idempotently.
- Model includes `PlanningApplyEvent`.
- Preview reports node count, total days, existing phases, hard errors, and
  preconditions.
- Apply creates phases with computed planned dates in topological order.
- Apply writes `planning_apply_events`.
- Apply writes project change log.
- Apply marks sandbox applied/read-only.
- Apply refuses active execution by actual start date.
- Apply refuses active execution by actual end date.
- Apply refuses active execution by `in_progress` / `done` / `delayed` status.
- Apply refuses active phase-linked blocker.
- Apply refuses invalid graph and zero-node sandbox.
- Apply deletes only phases matching the locked untouched predicate and counts
  skipped replacements correctly.
- Apply creates no `phase_plan_changes` rows.
- Apply updates planned launch only when selected.
- Apply route enforces edit permission.
- Viewer template does not render Apply affordances.
- AI tool registry does not register `apply_sandbox_to_project` in
  confirmation tools or handlers.
- Sandbox-only invariant holds before Apply.
- Timeline History includes a plan-applied event card.
- Browser smoke proves modal/panel exists, blocked state is readable, success
  state is visible, and mobile has no horizontal overflow.
- i18n parity is exact.

## Screenshots

Build 07 should generate:

- `test_artifacts/v14_build07_apply_modal_desktop.png`
- `test_artifacts/v14_build07_apply_snapshot_desktop.png`
- `test_artifacts/v14_build07_apply_mobile.png`

## Acceptance Criteria

- PM/admin can explicitly apply a valid draft sandbox to create the live phase
  plan.
- Existing active execution is never overwritten.
- Apply is audited in both `planning_apply_events` and project changes.
- Applied sandbox remains readable and non-editable.
- Timeline History surfaces the apply event.
- Project planned launch date changes only when explicitly requested.
- No Apply behavior is available to viewers or non-editing users.
- All new labels preserve exact i18n parity.

## Larger Scenario Contract Runner

The user's requested broader PM workflow test should be implemented during
v1.4 Build 09 release hardening, after Build 08 templates exist. Build 07
should add focused Apply tests only; the full scenario runner should later
simulate template selection, node edits, dependencies, tidy, Apply, Timeline
verification, save-as-template, and negative permission/active-execution cases.
