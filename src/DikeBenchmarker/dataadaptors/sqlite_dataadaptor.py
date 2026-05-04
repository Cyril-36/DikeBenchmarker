import polars as pl
import sqlite3
from typing import Optional


from DikeBenchmarker.dataadaptors.dataadaptor import DataAdaptor


__all__ = ["SqlDataAdaptor"]


class SqlDataAdaptor(DataAdaptor):
    """Implement the data adaptor for sqlite data."""

    def __init__(self, database_path: str):
        """Reads the database from DikeBenchmarker package."""
        self.database_path = database_path

    def get_performances(
        self,
        inst_hash: Optional[str] = None,
        solver_id: Optional[str] = None,
        env_id: Optional[str] = None,
        res_id: Optional[int] = None,
        filter: Optional[str] = None,
    ) -> pl.DataFrame:
        """Get as a DataFrame all performances for the specified inst_hash, solver_id, env_id, and res_id.

        If none are specified, returns all the data (not recommended).

        Args:
            inst_hash (str, optional): The id of the instance (inst_hash) to get the performances about.
            solver_id (str, optional): If set, only gives the performance with the specified solver_id. Defaults to None.
            env_id (str, optional): If set, only gives the performance with the specified env_id. Defaults to None.
            res_id (int, optional): If set, only gives the performance with the specified res_id. Defaults to None.
            filter (str): can contain 'no_inst_features' | 'no_env_features' | 'no_res_features' | 'no_solver_features' to omit the features of one aspect

        Returns:
            pl.DataFrame: A DataFrame containing the performances.
        """
        # Connect to the SQLite database (replace 'your_database.db' with your actual database file)
        conn = sqlite3.connect(self.database_path)

        try:
            # Base query
            query = (
                "SELECT p.perf, p.status,"
                + f"{'e.env_id' if filter == 'no_env_features' else 'e.*'},"
                + f"{'r.res_id' if filter == 'no_res_features' else 'r.*'},"
                + f"{'i.inst_hash' if filter == 'no_inst_features' else 'i.*'},"
                + f"{'s.solver_id' if filter == 'no_solver_features' else 's.*'}"
                + """
                FROM performances p
                LEFT JOIN environments e ON p.env_id = e.env_id
                LEFT JOIN resources r ON p.res_id = r.res_id
                LEFT JOIN instances i ON p.inst_hash = i.inst_hash
                LEFT JOIN solvers s ON p.solver_id = s.solver_id
            """
            )

            # List to hold conditions and parameters
            conditions = []
            params = []

            if inst_hash is not None:
                conditions.append("p.inst_hash = ?")
                params.append(inst_hash)
            if solver_id is not None:
                conditions.append("p.solver_id = ?")
                params.append(solver_id)
            if env_id is not None:
                conditions.append("p.env_id = ?")
                params.append(env_id)
            if res_id is not None:
                conditions.append("p.res_id = ?")
                params.append(res_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # Execute the query with parameters
            df = pl.read_database(query, conn, execute_options={"parameters": params})
            if "perf" in df.columns:
                df = df.with_columns(pl.col("perf").cast(pl.Float64))
            return df
        finally:
            conn.close()

    def get_competition_env(self, comp_name: str):
        """Returns the hash of the environment used during the given competition.

        Args:
            comp_name (str): Name of the competition track.

        Returns:
            Optional[str]: The environment hash, or None if not found.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.cursor()
            # Use parameterized query to avoid SQL injection
            query = "SELECT env_id, res_id FROM competition_compatibility WHERE competition = ?"
            cursor.execute(query, (comp_name,))
            result = cursor.fetchone()
            return (result[0], result[1]) if result else (None, None)
        finally:
            conn.close()

    def get_competition_solver_id(self, comp_name: str, solver_name: Optional[str] = None):
        """Get the solver id corresponding to the given solver name during the given competition.

        If no solver name is given, returns a list of all solver ids from the competition.

        Args:
            comp_name (str): Name of the competition.
            solver_name (Optional[str]): Name of the solver. If None, returns all solver ids.

        Returns:
            Union[str, List[str], None]: Solver id, list of solver ids, or None if not found.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.cursor()
            if solver_name:
                # Fetch the solver id for the given solver name and competition
                query = """
                    SELECT solver_id
                    FROM solvers
                    WHERE competition = ? AND solver_name = ?
                """
                cursor.execute(query, (comp_name, solver_name))
                result = cursor.fetchone()
                return result[0] if result else None
            else:
                # Fetch all solver ids for the competition
                query = """
                    SELECT solver_id
                    FROM solvers
                    WHERE competition = ?
                """
                cursor.execute(query, (comp_name,))
                results = cursor.fetchall()
                return [row[0] for row in results] if results else []
        finally:
            conn.close()

    def get_competitions(self) -> list[str]:
        """Returns the list of all competition names stored in the database.

        Returns:
            list[str]: List of competition names.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.cursor()
            query = """
                SELECT DISTINCT competition
                FROM solvers
                WHERE competition IS NOT NULL
                UNION
                SELECT DISTINCT competition
                FROM competition_compatibility
                WHERE competition IS NOT NULL
                ORDER BY competition
            """
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_competition_instance_hash(self, comp_name: str) -> list[str]:
        """Returns the list of instance hashes used in the given competition.

        Args:
            comp_name (str): Name of the competition track.

        Returns:
            list[str]: List of instance hashes.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.cursor()
            query = """
                SELECT DISTINCT p.inst_hash
                FROM performances p
                JOIN solvers s ON p.solver_id = s.solver_id
                JOIN competition_compatibility cc
                    ON cc.competition = s.competition
                    AND cc.env_id = p.env_id
                    AND cc.res_id = p.res_id
                WHERE s.competition = ?
                ORDER BY p.inst_hash
            """
            cursor.execute(query, (comp_name,))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_environments(self, env_ids: list) -> pl.DataFrame:
        """Returns the full environment rows for the given environment IDs.

        Args:
            env_ids: List of environment hashes.

        Returns:
            pl.DataFrame: DataFrame containing the environment rows.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            query = """
                SELECT *
                FROM environments
                WHERE env_id IN (?{})
            """.format(",?" * (len(env_ids) - 1))  # Parameterize for all env_ids
            return pl.read_database(query, conn, execute_options={"parameters": env_ids})
        finally:
            conn.close()

    def get_resources(self, res_ids: list) -> pl.DataFrame:
        """Returns the full resource rows for the given resource IDs.

        Args:
            res_ids: List of resource hashes.

        Returns:
            pl.DataFrame: DataFrame containing the resource rows.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            query = """
                SELECT *
                FROM resources
                WHERE res_id IN (?{})
            """.format(",?" * (len(res_ids) - 1))  # Parameterize for all res_ids
            return pl.read_database(query, conn, execute_options={"parameters": res_ids})
        finally:
            conn.close()

    def get_instances(self, inst_ids: list) -> pl.DataFrame:
        """Returns the full instance rows for the given instance IDs.

        Args:
            inst_ids: List of instance hashes.

        Returns:
            pl.DataFrame: DataFrame containing the instance rows.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            query = """
                SELECT *
                FROM instances
                WHERE inst_hash IN (?{})
            """.format(",?" * (len(inst_ids) - 1))  # Parameterize for all inst_ids
            return pl.read_database(query, conn, execute_options={"parameters": inst_ids})
        finally:
            conn.close()

    def get_solvers(self, solver_ids: list) -> pl.DataFrame:
        """Returns the full solver rows for the given solver IDs.

        Args:
            solver_ids: List of solver hashes.

        Returns:
            pl.DataFrame: DataFrame containing the solver rows.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            query = """
                SELECT *
                FROM solvers
                WHERE solver_id IN (?{})
            """.format(",?" * (len(solver_ids) - 1))  # Parameterize for all solver_ids
            return pl.read_database(query, conn, execute_options={"parameters": solver_ids})
        finally:
            conn.close()

    def get_all_instance_ids(self) -> list[str]:
        """Returns a list of all instance IDs in the database.

        Returns:
            list[str]: List of all instance hashes.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.cursor()
            query = "SELECT inst_hash FROM instances"
            cursor.execute(query)
            results = cursor.fetchall()
            return [row[0] for row in results]
        finally:
            conn.close()

    def get_all_solver_ids(self) -> list[str]:
        """Returns a list of all solver IDs in the database.

        Returns:
            list[str]: List of all solver hashes.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.cursor()
            query = "SELECT solver_id FROM solvers"
            cursor.execute(query)
            results = cursor.fetchall()
            return [row[0] for row in results]
        finally:
            conn.close()

    def bulk_load_performances(self, inst_ids: list[str], solver_ids: list[str]) -> dict:
        """Load all (inst_hash, solver_id) -> perf pairs in a single SQL query.

        Args:
            inst_ids: List of instance hashes to include.
            solver_ids: List of solver IDs to include.

        Returns:
            dict mapping (inst_hash, solver_id) -> float perf value.
        """
        conn = sqlite3.connect(self.database_path)
        try:
            inst_placeholders = ",".join("?" * len(inst_ids))
            sol_placeholders = ",".join("?" * len(solver_ids))
            query = f"SELECT p.inst_hash, p.solver_id, p.perf FROM performances p WHERE p.inst_hash IN ({inst_placeholders}) AND p.solver_id IN ({sol_placeholders})"
            cursor = conn.cursor()
            cursor.execute(query, inst_ids + solver_ids)
            return {(row[0], row[1]): row[2] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_solvers_covering_instances(self, inst_hashes: list[str]) -> list[str]:
        """Returns a list of solver IDs that have performance data for all the given instance hashes."""
        if not inst_hashes:
            return []

        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.cursor()

            inst_hashes = list(set(inst_hashes))
            inst_str = ",".join("?" for _ in inst_hashes)

            query = f"""
                SELECT p.solver_id
                FROM performances p
                WHERE p.inst_hash IN ({inst_str})
                GROUP BY p.solver_id
                HAVING COUNT(DISTINCT p.inst_hash) = ?
            """

            cursor.execute(query, (*inst_hashes, len(inst_hashes)))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
