# DM Design Quest Publishing Plan

## Feature Design Review

1. **Real workflow problem:** A Designer Manager currently has to ask a PM to create and publish every design quest even though the DM owns day-to-day design operations.
2. **Repeated or edge-case:** This is a repeated workflow for every new design assignment.
3. **Structured data:** No new structured data is needed because Design Quest already stores the required fields.
4. **Journal/notes alternative:** Notes cannot replace a published quest because designers need the existing assignment and submission workflow.
5. **Intake burden:** The DM uses the same compact quest fields already used by PMs.
6. **AI reduction:** AI publishing remains deferred; this change is manual and audited.
7. **Display/reminder payoff:** The manager console shows projects available for a quest and draft quests waiting to be published.
8. **Migration impact:** None.
9. **Minimal schema change:** None.
10. **Minimal UI change:** Add one create form and one draft-publish list to `/designer/manager`.
11. **Deferred:** Full PM Workspace access, project editing, reference-file management, AI quest writes, and expanded submission review remain deferred.
12. **Primary click-path:** Designer Portal -> Manager operations -> Create task draft -> Publish -> task appears in Designer Portal.
13. **Reference scan:** Skipped because this extends the existing PM Design Quest workflow.
14. **Locked behaviors:** DM can create and publish Design Quests from the manager console; regular designers cannot; DM still cannot open `/projects/:id`; only project name and quest workflow fields are exposed.
15. **Automated locks:** `test_v15_build09.py` verifies DM create/publish, designer rejection, published visibility, safe manager-page data, and continued project-page blocking.

