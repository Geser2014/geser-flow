# Design: Project Stages (Этапы проектов)

## Summary

Add hierarchical project structure: Project -> Stages. Each project has one or more stages. Sessions are tracked per stage, statistics aggregated at both levels.

## Database Changes

### New table: `stages`

| Column     | Type      | Constraints                    |
|------------|-----------|--------------------------------|
| id         | INTEGER   | PRIMARY KEY AUTOINCREMENT      |
| project_id | INTEGER   | NOT NULL, FK -> projects(id)   |
| name       | TEXT      | NOT NULL                       |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP      |

- UNIQUE constraint on (project_id, name) — stage names unique within a project.

### Modified table: `sessions`

- Add column `stage_id` (INTEGER, FK -> stages(id), nullable for migration).

### Migration

- For each existing project, create a stage named "Общее".
- Set `stage_id` on all existing sessions to the corresponding "Общее" stage.

## Main Window (Idle Screen)

### Project selector
- Replace text input with CTkOptionMenu (dropdown).
- Items order: "Новый проект..." first, then projects sorted by most recent session (descending).
- On launch: last used project selected by default.
- Selecting "Новый проект..." shows a text input field for the name. On confirm, project + default stage "Общее" are created.

### Stage selector
- New CTkOptionMenu below project selector.
- Items order: "Новый этап..." first, then stages of selected project sorted by most recent session (descending).
- On launch: last used stage selected by default.
- Selecting "Новый этап..." shows a text input field for the name. On confirm, stage is created under current project.
- When project changes, stage dropdown refreshes with that project's stages.

### Session start
- `start_session()` now receives both project name and stage name (or IDs).
- Session record includes `stage_id`.

## Dashboard

### Project rows
- Each row in the table represents a project with aggregated stats (same columns as now).
- New "▼" button at the right side of each row.

### Stage expansion
- Double-click on project row OR click "▼" button to expand/collapse.
- Expanded: shows sub-rows for each stage below the project row.
- Stages ordered by `created_at` ascending (first created on top).
- Stage sub-rows have the same columns as project rows.
- "▼" toggles to "▲" when expanded.

### Stats columns (both project and stage rows)
- Same columns used at both levels. Exact columns depend on current dashboard implementation (date range, work time, pauses, breaks, session count).

## Backward Compatibility

- Existing sessions get assigned to auto-created "Общее" stages during migration.
- No data loss.

## Out of Scope

- Nesting deeper than Project -> Stage.
- Reordering or renaming stages.
- Archiving/deleting stages.
