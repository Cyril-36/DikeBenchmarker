import sqlite3

import pytest
import polars as pl
import importlib.resources
from DikeBenchmarker.dataadaptors.sqlite_dataadaptor import SqlDataAdaptor


@pytest.fixture
def db_path():
    # Use importlib.resources to get the path to the test database
    with importlib.resources.files("DikeBenchmarker.data.db").joinpath("sustainablecompetition.db") as db_file:
        return str(db_file)


@pytest.fixture
def adaptor(db_path):
    return SqlDataAdaptor(db_path)


def test_get_performances(adaptor, db_path):
    print(db_path)
    # Test with all optional arguments
    df = adaptor.get_performances(inst_hash="00d1fe07ab948b348bb3fb423b1ef40d", solver_id="AMSAT_main2024", env_id="starexec2024")
    assert isinstance(df, pl.DataFrame)
    assert not df.is_empty()

    # Test with no arguments (should return all performances)
    df_all = adaptor.get_performances()
    assert isinstance(df_all, pl.DataFrame)


def test_get_competition_env(adaptor):
    env_id, res_id = adaptor.get_competition_env("main2024")
    assert env_id is not None
    assert isinstance(env_id, str)
    assert res_id is not None
    assert isinstance(res_id, int)


def test_get_competition_solver_id(adaptor):
    # Test with solver_name
    print(adaptor.database_path)
    solver_id = adaptor.get_competition_solver_id("main2024", solver_name="AMSAT")
    assert solver_id is not None
    assert isinstance(solver_id, str)

    # Test without solver_name (should return a list)
    solver_ides = adaptor.get_competition_solver_id("main2024")
    assert isinstance(solver_ides, list)
    assert all(isinstance(h, str) for h in solver_ides)


def test_get_environments(adaptor):
    df = adaptor.get_environments(["starexec2024", "starexec2022"])
    assert isinstance(df, pl.DataFrame)
    assert not df.is_empty()


def test_get_instances(adaptor):
    df = adaptor.get_instances(["27f381d4d67c90c8c6a6a186cd51e94a", "28674e12b109f3b3e2967e5770184def"])
    assert isinstance(df, pl.DataFrame)
    assert not df.is_empty()


def test_get_solvers(adaptor):
    df = adaptor.get_solvers(["AMSAT_main2024", "IsaSAT_main2024"])
    assert isinstance(df, pl.DataFrame)
    assert not df.is_empty()


def test_get_all_instance_ids(adaptor):
    inst_ids = adaptor.get_all_instance_ids()
    assert isinstance(inst_ids, list)
    assert all(isinstance(i, str) for i in inst_ids)


def test_get_all_solver_ids(adaptor):
    solver_ids = adaptor.get_all_solver_ids()
    assert isinstance(solver_ids, list)
    assert all(isinstance(i, str) for i in solver_ids)


def test_get_competitions_from_solver_and_compatibility_sources(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE solvers (solver_id TEXT, competition TEXT, solver_name TEXT)")
        cursor.execute("CREATE TABLE competition_compatibility (competition TEXT, env_id TEXT, res_id INTEGER)")
        cursor.execute("INSERT INTO solvers VALUES ('solver_a', 'comp_from_solvers', 'Solver A')")
        cursor.execute("INSERT INTO competition_compatibility VALUES ('comp_from_compatibility', 'env_a', 1)")
        conn.commit()
    finally:
        conn.close()
    adaptor = SqlDataAdaptor(str(db_path))
    competitions = adaptor.get_competitions()
    assert competitions == ["comp_from_compatibility", "comp_from_solvers"]


def test_get_competition_instance_hash_filters_by_competition_environment_and_resource(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE solvers (solver_id TEXT, competition TEXT, solver_name TEXT)")
        cursor.execute("CREATE TABLE competition_compatibility (competition TEXT, env_id TEXT, res_id INTEGER)")
        cursor.execute("CREATE TABLE performances (inst_hash TEXT, solver_id TEXT, env_id TEXT, res_id INTEGER, perf REAL, status TEXT)")
        cursor.execute("INSERT INTO solvers VALUES ('solver_a', 'comp_a', 'Solver A')")
        cursor.execute("INSERT INTO solvers VALUES ('solver_b', 'comp_b', 'Solver B')")
        cursor.execute("INSERT INTO competition_compatibility VALUES ('comp_a', 'env_a', 1)")
        cursor.execute("INSERT INTO competition_compatibility VALUES ('comp_b', 'env_b', 2)")
        cursor.execute("INSERT INTO performances VALUES ('inst_a', 'solver_a', 'env_a', 1, 1.0, 'COMPLETE')")
        cursor.execute("INSERT INTO performances VALUES ('inst_extra', 'solver_a', 'env_b', 2, 1.0, 'COMPLETE')")
        cursor.execute("INSERT INTO performances VALUES ('inst_b', 'solver_b', 'env_b', 2, 1.0, 'COMPLETE')")
        conn.commit()
    finally:
        conn.close()
    adaptor = SqlDataAdaptor(str(db_path))
    assert adaptor.get_competition_instance_hash("comp_a") == ["inst_a"]
    assert adaptor.get_competition_instance_hash("comp_b") == ["inst_b"]
    assert adaptor.get_competition_instance_hash("nonexistent") == []
