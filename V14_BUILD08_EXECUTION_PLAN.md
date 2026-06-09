# v1.4 Build 08 Execution Plan - Save Workflow As Template

## Status

Execution plan for the eighth v1.4 Planning Sandbox implementation build.

Predecessor: v1.4 Build 07 - Apply Sandbox To Project Plan.

Successor: v1.4 Build 09 - Release Hardening.

Canonical design references:
- `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` section 13 route/service table,
  section 14 permission model, Q10 template ownership rules, and the v1.4-08
  build row.
- `V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md` section "v1.4 Build 08 - Save
  Workflow As Template".

## Purpose

Build 08 lets PMs turn a useful sandbox workflow into a reusable template for
future knife projects. This is a template-library mutation only: it must not
change the live project timeline, active phases, apply events, or project
launch dates.

## Scope

In:

1. Add service helpers in `app/crud.py`:
   - `list_planning_templates_for_user`
   - `save_sandbox_as_template`
   - private template-key generation / visibility helpers as needed
2. Add POST route in `app/routes/projects.py`:
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/save-template`
3. Update the sandbox page:
   - show Save as Template affordance for editable draft/applied sandboxes,
   - hide Save as Template for viewers and archived sandboxes,
   - add a compact save-template form/panel with required name and optional
     description,
   - show success/error messages after redirect,
   - group template picker rows as System Templates and My Templates.
4. Update template picker data to include visible user templates:
   - system templates visible to all authenticated users,
   - user's own active templates visible to that user,
   - admin can see all active user templates.
5. Update `AI_TOOLS_REGISTRY.md` with a planned/deferred tool row for
   `save_sandbox_as_template`; do not wire an AI handler in Build 08.
6. Add EN/zh i18n keys with exact parity.
7. Add `test_v14_build08.py`.

Out:

- No new migrations unless implementation discovers a hard blocker in the
  existing template schema.
- No template edit/delete UI.
- No system-template editing or overwriting.
- No project-scoped templates.
- No Apply behavior changes.
- No live `project_phases` mutation.
- No `planning_apply_events` writes.
- No AI chat handler or silent AI template creation.
- No multiple-draft sandbox support.
- No new dependency types beyond `finish_to_start`.

## Architecture Review

1. Problem solved: PMs need to reuse a proven or customized workflow instead
   of rebuilding the same timeline graph for similar projects.
2. Tables affected: writes `planning_templates`, `planning_template_nodes`,
   and `planning_template_edges`; reads `planning_sandboxes`,
   `planning_sandbox_nodes`, `planning_sandbox_edges`, `users`, and `projects`.
3. Real data vs notes: reusable workflow graphs are structured data with nodes,
   edges, ownership, and picker visibility, so they cannot safely live in notes.
4. Service layer: all template creation, cloning, permission filtering, and
   template-key generation live in `crud.py`; routes only parse form input and
   redirect.
5. Change log: no project change log is required because saving a template does
   not mutate project execution state. The template rows themselves are the
   source of truth.
6. Rollback: the build is additive row creation in already-existing template
   tables; templates can be deactivated later and no live project data is
   changed.

## Feature Design Review

1. Real problem: PMs need reusable sandbox workflows for repeated knife
   development patterns.
2. Repeated use: every new project can start from a saved workflow instead of a
   blank canvas.
3. Structured data: templates must store reusable nodes, edges, durations,
   owners, deliverables, and exit criteria.
4. Notes fallback: notes cannot preserve graph dependencies or drive future
   schedule calculations.
5. Intake burden: saving a known workflow reduces future planning work.
6. AI role: AI may eventually suggest or save templates, but Build 08 keeps AI
   manual/deferred and confirmation-only.
7. Display payoff: PMs see their own templates in the picker immediately after
   saving.
8. Migration impact: none expected because template tables already exist.
9. Minimal schema: use existing template tables; do not add schema for custom
   category/phase metadata unless tests expose an unavoidable loss.
10. Minimal UI change: add one save panel and template-picker grouping on the
    sandbox page only.
11. Deferred: template editing/deletion, organization-wide template publishing,
    project-scoped templates, AI handler, and richer template analytics.

## Backend Honesty Mapping

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Save as Template button | sandbox status + project edit access | none until form submit | visible only for `draft` or `applied` sandbox when `can_edit_project` | PM/admin project editors | template + browser test |
| Template name | form input | `save_sandbox_as_template` writes `planning_templates.name` | required, trimmed, max length enforced by service | PM/admin project editors | service + route validation |
| Template description | form input | `planning_templates.description` | optional, trimmed | PM/admin project editors | service test |
| Template key | generated by service | `planning_templates.template_key` | slug from name plus short unique suffix; never user-supplied | service only | uniqueness test |
| Template ownership badge | `planning_templates.is_system` and `created_by_user_id` | service writes user templates as non-system | system first, then visible user templates | all authenticated viewers of picker | picker render test |
| Saved template nodes | current `planning_sandbox_nodes` | copied to `planning_template_nodes` | preserve module key, title, duration, owner, deliverable, exit criteria, position, sort order | PM/admin project editors | graph-copy test |
| Saved template edges | current `planning_sandbox_edges` | copied to `planning_template_edges` | preserve in-template edge topology and dependency type | PM/admin project editors | graph-copy test |
| Create sandbox from saved template | visible template rows | existing `create_sandbox_from_template` | clones visible user/system template graph into draft sandbox | PM/admin project editors | create-from-saved-template test |
| Viewer picker | visible templates | no write path | viewers see picker inventory but no create/save mutation affordances | authenticated view only | template assertion |
| AI tool registry row | `AI_TOOLS_REGISTRY.md` | docs-only in Build 08 | planned/deferred manual equivalent, no handler | n/a | registry/source test |

## Locked Implementation Decisions

1. **No migration by default.** Existing template tables are the intended Build
   08 storage. If implementation discovers a schema-loss blocker, stop and
   report instead of quietly adding columns.
2. **Templates are global reusable records, not project-scoped records.**
   `planning_templates.created_by_user_id` controls user ownership; no project
   id is added.
3. **System templates are immutable.** Build 08 creates only
   `is_system=False` templates and never overwrites existing system rows.
4. **Template keys are service-generated.** The UI never submits
   `template_key`; duplicate names produce unique keys.
5. **Saved graph must be reusable by the existing clone path.** Because
   `PlanningTemplateNode` currently does not store `category` or `phase_type`,
   Build 08 must preserve `module_key` for module-based nodes so
   `create_sandbox_from_template` can derive category/phase type from
   `PlanningModule`.
6. **No bespoke-node schema expansion in this build.** If a sandbox node lacks a
   module key, the service may still save it as a template node with its title
   and duration, but any phase type fallback follows the existing clone behavior.
   Rich custom-module preservation is deferred.
7. **Draft and applied snapshots can be saved.** Draft sandboxes capture work in
   progress; applied sandboxes capture proven workflows. Archived sandboxes are
   read-only and do not show the Save as Template affordance.
8. **Saving a template does not affect the project timeline.** No
   `ProjectPhase`, `PlanningApplyEvent`, launch-date, or phase-plan-change
   writes happen.
9. **Template picker respects visibility.** User templates are visible to their
   creator and admins. Non-admin users do not see other users' private
   templates.
10. **Viewers do not see dead buttons.** Viewer users can inspect the sandbox
    and template inventory, but Save/Create mutation controls are hidden.
11. **AI is documented, not wired.** Add a planned/deferred registry row for
    `save_sandbox_as_template`; no `app/ai/tools.py` schema or handler is added
    in Build 08.

## Service Contract

`crud.save_sandbox_as_template(db, project_id, sandbox_id, name, description,
user_id) -> PlanningTemplate` must:

1. Load sandbox by `project_id` and `sandbox_id`.
2. Refuse missing sandbox with `sandbox_not_found`.
3. Refuse archived sandbox with `sandbox_not_templateable`.
4. Validate name is non-empty after trim; otherwise raise `template_name_required`.
5. Generate a unique, stable-enough `template_key` from the name and a short
   suffix.
6. Insert a `PlanningTemplate` row:
   - `is_system=False`
   - `created_by_user_id=user_id`
   - `is_active=True`
   - `sort_order` after current visible/system templates
7. Copy sandbox nodes to template nodes in sort order.
8. Copy sandbox edges using an old-node-id to new-template-node-id map.
9. Commit once and return the template.

`crud.list_planning_templates_for_user(db, user, active_only=True)` must:

1. Include all active system templates.
2. Include active user templates created by the current user.
3. Include all active user templates for admins.
4. Order system templates first by `sort_order/name`, then user templates by
   newest created date or sort order/name if implementation keeps current
   ordering.

## Route Contract

`POST /projects/{project_id}/sandbox/{sandbox_id}/save-template`

Form fields:
- `template_name`
- `template_description`

Behavior:
- auth required,
- `can_edit_project(current_user, project)` required,
- project/sandbox relationship required,
- delegates to `crud.save_sandbox_as_template`,
- redirects back to `/projects/{project_id}/sandbox/{sandbox_id}?template_saved=1`
  on success,
- redirects with `error=template_name_required`, `error=not_authorized`,
  `error=sandbox_not_templateable`, or `error=template_save_failed` on failure.

## UX Behavior

- Sandbox toolbar or side panel shows **Save as Template** when the current user
  can edit the project and the sandbox status is `draft` or `applied`.
- The form is compact and does not interrupt canvas work:
  - template name required,
  - template description optional,
  - Save button,
  - short explanatory copy that this saves a reusable workflow and does not
    change the live project timeline.
- Success message confirms the template was saved and is available in the
  template picker.
- Template picker groups:
  - System Templates,
  - My Templates.
- User template rows show a lightweight "My template" badge.
- Viewers do not see Save or Create mutation affordances.

## i18n Lock

Build 08 adds exactly 14 keys. If current parity is 791/791, expected parity
after implementation is 805/805.

| Key | EN | ZH |
|---|---|---|
| `sandbox.save_template` | Save as Template | 保存为模板 |
| `sandbox.save_template_title` | Save Workflow as Template | 保存工作流模板 |
| `sandbox.save_template_body` | Save this sandbox workflow for future projects. This will not change the live timeline. | 将此沙盒工作流保存给未来项目使用。不会修改当前正式时间线。 |
| `sandbox.template_name` | Template name | 模板名称 |
| `sandbox.template_description` | Description | 描述 |
| `sandbox.template_name_required` | Template name is required. | 请输入模板名称。 |
| `sandbox.save_template_success` | Template saved. It is now available in the template picker. | 模板已保存，可在模板选择器中使用。 |
| `sandbox.save_template_error` | Template could not be saved. | 模板未能保存。 |
| `sandbox.system_templates` | System Templates | 系统模板 |
| `sandbox.my_templates` | My Templates | 我的模板 |
| `sandbox.user_template_badge` | My template | 我的模板 |
| `sandbox.no_user_templates` | No saved templates yet. | 暂无已保存模板。 |
| `sandbox.template_saved_from` | Saved from sandbox | 来源：沙盒 |
| `sandbox.template_not_available` | Template is not available. | 模板不可用。 |

## AI Tools Registry Update

Add one planned/deferred row to `AI_TOOLS_REGISTRY.md`:

| Tool | Purpose | Permission | Confirmation | Target Build |
|---|---|---|---|---|
| `save_sandbox_as_template` | Save the current planning sandbox graph as a reusable workflow template | auth + `can_edit_project` + visible sandbox relationship + user confirmation | YES | deferred after v1.4 manual UI |

No `app/ai/tools.py` schema, dispatcher handler, or chat prompt changes in
Build 08.

## Test Plan

Create `test_v14_build08.py` covering:

1. Source locks:
   - save-template route exists,
   - `save_sandbox_as_template` exists,
   - `list_planning_templates_for_user` exists,
   - no AI tool handler/schema is registered for save-template.
2. Migration/schema:
   - no new migration is required,
   - template tables from Build 01 remain present.
3. Service tests:
   - saves template from a draft sandbox with nodes and edges,
   - saves template from an applied sandbox,
   - refuses archived sandbox,
   - refuses blank/empty template name,
   - duplicate template names create unique keys,
   - saved node/edge graph matches source sandbox,
   - saved template can create a new draft sandbox through
     `create_sandbox_from_template`.
4. Permission/visibility tests:
   - system templates visible to all authenticated users,
   - creator sees own user templates,
   - non-owner non-admin does not see another user's private template,
   - admin sees user templates,
   - viewer cannot call save route and sees no Save/Create affordances.
5. Route tests:
   - successful POST redirects with `template_saved=1`,
   - invalid name redirects with `error=template_name_required`,
   - unauthorized save redirects with `error=not_authorized`.
6. UI/browser tests:
   - Save as Template panel renders for editable draft/applied sandbox,
   - My Templates group renders after save,
   - mobile sandbox page has no horizontal overflow.
7. i18n:
   - exact EN/zh key parity,
   - Build 08 key count reaches 805/805 if current base remains 791/791.
8. Baselines:
   - `python3 test_v14_build08.py`
   - `python3 test_v14_build07.py`
   - `python3 test_v14_build06.py`
   - `python3 test_build_v121.py`
   - `git diff --check`

## Acceptance Criteria

- PM/admin can save a draft or applied sandbox as a reusable user template.
- The saved template appears in the picker immediately under My Templates.
- Starting a new sandbox from the saved template reproduces the graph.
- System templates remain immutable.
- Non-owner users cannot see or mutate private user templates.
- Viewers see no mutation affordances.
- No live Timeline/project phase data changes during template save.
- AI registry documents the future tool surface, but no AI write path exists.
- Tests and i18n parity pass.

## Remaining Manual Review

- Confirm with PMs whether saved user templates should remain private to the
  creator or later gain a "publish to team" flow.
- Confirm whether applied snapshots are desirable save sources after real use.
- Decide in a future build whether custom/bespoke nodes need full template
  schema preservation for `category` and `phase_type`.
