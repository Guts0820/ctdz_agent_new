from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

class Neo4jConnection:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver = None

    def connect(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        try:
            self.driver.verify_connectivity()
            print("Successfully connected to Neo4j")
        except Exception as e:
            print(f"Connection failed: {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def query(self, cypher_query, parameters=None):
        if not self.driver:
            self.connect()
        if not self.driver:
            raise Exception("Failed to connect to Neo4j")
        
        with self.driver.session(database=self.database) as session:
            result = session.run(cypher_query, parameters or {})
            return [record.data() for record in result]

neo4j_conn = Neo4jConnection()