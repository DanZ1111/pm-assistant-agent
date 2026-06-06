"""v1.4 Build 02 — Planning Sandbox schedule engine regression."""
import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = [], []


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def build_db():
    tmp = tempfile.TemporaryDirectory()
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'schedule.db'}")
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def create_project(db, name="Schedule Project"):
    from app.models import Project
    project = Project(name=name, status="active")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_sandbox(db, project_id, name="Sandbox", status="draft"):
    from app.models import PlanningSandbox
    sandbox = PlanningSandbox(project_id=project_id, name=name, status=status)
    db.add(sandbox)
    db.commit()
    db.refresh(sandbox)
    return sandbox


def add_node(db, sandbox_id, title, duration, phase_type="design", owner="pm",
             deliverable="deliverable", exit_criteria="done", order=0):
    from app.models import PlanningSandboxNode
    node = PlanningSandboxNode(
        sandbox_id=sandbox_id,
        title=title,
        phase_type=phase_type,
        category="PRODUCT",
        duration_days=duration,
        owner_role=owner,
        deliverable=deliverable,
        exit_criteria=exit_criteria,
        sort_order=order,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def add_edge(db, sandbox_id, from_node, to_node):
    from app.models import PlanningSandboxEdge
    edge = PlanningSandboxEdge(
        sandbox_id=sandbox_id,
        from_node_id=from_node.id,
        to_node_id=to_node.id,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


def codes(result, bucket="hard_errors"):
    return {entry["code"] for entry in result[bucket]}


def fixture_session():
    tmp, engine, Session = build_db()
    db = Session()
    project = create_project(db)
    sandbox = create_sandbox(db, project.id)
    return tmp, engine, db, project, sandbox


def main():
    import app.crud as crud

    print("\n── 1. Linear graph estimate ──")
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        a = add_node(db, sandbox.id, "Design", 5, "design", order=1)
        b = add_node(db, sandbox.id, "Prototype", 10, "prototype", order=2)
        c = add_node(db, sandbox.id, "Launch", 1, "launch", order=3)
        add_edge(db, sandbox.id, a, b)
        add_edge(db, sandbox.id, b, c)
        result = crud.compute_sandbox_schedule(db, sandbox.id, require_nodes=True)
        if not result["hard_errors"] and result["total_days"] == 16 and result["terminal_node_ids"] == [c.id]:
            ok("Linear graph sums durations and finds launch terminal")
        else:
            fail("linear graph", result)
    finally:
        db.close(); tmp.cleanup()

    print("\n── 2. Parallel fork/join + multi-parent blocking path ──")
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        design = add_node(db, sandbox.id, "Design", 14, "design", order=1)
        engineering = add_node(db, sandbox.id, "Engineering", 24, "engineering", order=2)
        sample = add_node(db, sandbox.id, "Sample", 21, "prototype", order=3)
        launch = add_node(db, sandbox.id, "Launch", 1, "launch", order=4)
        add_edge(db, sandbox.id, design, sample)
        add_edge(db, sandbox.id, engineering, sample)
        add_edge(db, sandbox.id, sample, launch)
        result = crud.compute_sandbox_schedule(db, sandbox.id)
        sample_row = next(n for n in result["nodes"] if n["id"] == sample.id)
        if result["total_days"] == 46 and sample_row["start_day"] == 24 and sample_row["end_day"] == 45:
            ok("Multi-parent node waits for longest upstream branch")
        else:
            fail("fork/join estimate", result)
    finally:
        db.close(); tmp.cleanup()

    print("\n── 3. Disconnected branches ──")
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        add_node(db, sandbox.id, "Design Branch", 10, "design", order=1)
        add_node(db, sandbox.id, "Packaging Branch", 17, "packaging", order=2)
        result = crud.compute_sandbox_schedule(db, sandbox.id)
        if result["total_days"] == 17 and result["connected_component_count"] == 2 and "disconnected_branch" in codes(result, "soft_warnings"):
            ok("Disconnected branches run from day 0 and warn softly")
        else:
            fail("disconnected branches", result)
    finally:
        db.close(); tmp.cleanup()

    print("\n── 4. Hard validation errors ──")
    # cycle
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        a = add_node(db, sandbox.id, "A", 1, order=1)
        b = add_node(db, sandbox.id, "B", 1, order=2)
        add_edge(db, sandbox.id, a, b)
        add_edge(db, sandbox.id, b, a)
        result = crud.compute_sandbox_schedule(db, sandbox.id)
        if "circular_dependency" in codes(result):
            ok("Cycle detection blocks schedule")
        else:
            fail("cycle detection", result)
    finally:
        db.close(); tmp.cleanup()

    # dangling edge + invalid title/duration + zero-node require flag
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        bad = add_node(db, sandbox.id, " ", 0, order=1)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO planning_sandbox_edges "
                "(sandbox_id, from_node_id, to_node_id, dependency_type, created_at) "
                "VALUES (:sid, :from_id, :to_id, 'finish_to_start', CURRENT_TIMESTAMP)"
            ), {"sid": sandbox.id, "from_id": bad.id, "to_id": 999999})
        result = crud.compute_sandbox_schedule(db, sandbox.id, require_nodes=True)
        hard = codes(result)
        if {"missing_title", "invalid_duration", "dangling_edge"}.issubset(hard):
            ok("Missing title, invalid duration, and dangling edge are hard errors")
        else:
            fail("hard validation combo", result)
        empty_project = create_project(db, name="Empty Project")
        empty = create_sandbox(db, empty_project.id, name="Empty")
        empty_result = crud.compute_sandbox_schedule(db, empty.id, require_nodes=True)
        relaxed_result = crud.compute_sandbox_schedule(db, empty.id, require_nodes=False)
        if "zero_nodes" in codes(empty_result) and "zero_nodes" not in codes(relaxed_result):
            ok("Zero-node error only fires for apply-style validation")
        else:
            fail("zero node validation", {"required": empty_result, "relaxed": relaxed_result})
    finally:
        db.close(); tmp.cleanup()

    # cross-sandbox edge
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        other = create_sandbox(db, project.id, name="Other", status="archived")
        a = add_node(db, sandbox.id, "A", 1, order=1)
        b = add_node(db, other.id, "B", 1, order=1)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO planning_sandbox_edges "
                "(sandbox_id, from_node_id, to_node_id, dependency_type, created_at) "
                "VALUES (:sid, :from_id, :to_id, 'finish_to_start', CURRENT_TIMESTAMP)"
            ), {"sid": sandbox.id, "from_id": a.id, "to_id": b.id})
        result = crud.compute_sandbox_schedule(db, sandbox.id)
        if "cross_sandbox_edge" in codes(result):
            ok("Cross-sandbox edge is a hard error")
        else:
            fail("cross sandbox edge", result)
    finally:
        db.close(); tmp.cleanup()

    print("\n── 5. Semantic soft warnings ──")
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        packaging = add_node(db, sandbox.id, "Packaging", 10, "packaging", order=1)
        production = add_node(db, sandbox.id, "Production", 30, "production", order=2)
        long = add_node(db, sandbox.id, "Long Research", 70, "engineering",
                        owner=None, deliverable=None, exit_criteria=None, order=3)
        add_edge(db, sandbox.id, packaging, production)
        result = crud.compute_sandbox_schedule(db, sandbox.id)
        soft = codes(result, "soft_warnings")
        expected = {
            "packaging_before_design",
            "production_before_sample",
            "terminal_not_launch_like",
            "very_long_duration",
            "missing_owner",
            "missing_deliverable",
            "missing_exit_criteria",
        }
        if expected.issubset(soft):
            ok("Semantic warning set covers ordering, terminal, long, and missing-field cases")
        else:
            fail("semantic warnings", sorted(soft))
    finally:
        db.close(); tmp.cleanup()

    print("\n── 6. No live project phase mutation ──")
    tmp, engine, db, project, sandbox = fixture_session()
    try:
        add_node(db, sandbox.id, "Design", 5, "design", order=1)
        before = db.execute(text("SELECT COUNT(*) FROM project_phases")).scalar()
        crud.compute_sandbox_schedule(db, sandbox.id, require_nodes=True)
        after = db.execute(text("SELECT COUNT(*) FROM project_phases")).scalar()
        if before == after == 0:
            ok("compute_sandbox_schedule does not touch project_phases")
        else:
            fail("project phase mutation", f"before={before} after={after}")
    finally:
        db.close(); tmp.cleanup()

    print("\n── Summary ──")
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
