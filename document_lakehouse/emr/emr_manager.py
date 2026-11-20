
import logging
from typing import Any, List

from boto3.session import Session
from pyspark.sql import SparkSession

import boto3
from botocore.waiter import create_waiter_with_client, WaiterModel
from botocore.exceptions import ClientError


log = logging.getLogger(__name__)


class EMRSparkManager:
    """Manage Amazon EMR clusters and Spark Connect sessions."""

    def __init__(
        self,
        region_name: str,
        cluster_id: str | None = None,
        session: Session | None = None,
    ):
        self.region_name = region_name
        self.cluster_id = cluster_id

        self.session = session or boto3.Session(
            region_name=region_name
        )

        self.emr = self.session.client("emr")

        # Spark Connect state
        self.session_id = None
        self.spark: SparkSession | None = None
        self.endpoint = None
        self.auth_token = None

    # ==========================================
    # Cluster Configuration
    # ==========================================

    def build_cluster_config(
        self,
        name: str,
        release_label: str,
        instances_role: List[str],
        instances_type: List[str],
        instances_count: List[int],
        # log_uri: str,
        subnet_id: str,
        service_role: str,
        job_flow_role: str,
    ) -> dict:
        """Build EMR cluster configuration."""
        config = {
            "Name": name,
            "ReleaseLabel": release_label,
            "Instances": {
                "InstanceGroups": [
                    {
                        "InstanceRole": instance_role,
                        "InstanceType": instance_type,
                        "InstanceCount": instance_count,

                    } for instance_role, instance_type, instance_count in zip(instances_role, instances_type, instances_count)
                ],
                "Ec2SubnetId": subnet_id,
            },
            "ServiceRole": service_role,
            "JobFlowRole": job_flow_role,
            "SessionEnabled": True,
            "Tags": [
                {
                    "Key": "for-use-with-amazon-emr-managed-policies",
                    "Value": "true"
                }
            ]
        }

        return config

    # ==========================================
    # Cluster Lifecycle
    # ==========================================

    def create_cluster(
        self,
        config: dict,
    ) -> str:
        """Create an EMR cluster and return its ID."""
        try:
            response = self.emr.run_job_flow(**config)
            self.cluster_id = response["JobFlowId"]

            self.wait_for_cluster(self.cluster_id, "WAITING")
        except ClientError as e:
            log.error("could not create EMR cluster: %s", e)
        else:
            return self.cluster_id

    def describe_cluster(self) -> dict:
        """Retrieve cluster configuration and status."""
        if self.cluster_id is None:
            log.warning("cluster %s does not exist", self.cluster_id)
            return None
        else:
            try:
                response = self.client.describe_cluster(ClusterId=self.cluster_id)
                cluster = response["Cluster"]
            except ClientError as e:
                log.error("unexpected error: %s", e)
            else:
                return cluster

    def list_clusters(
        self,
        states: list[str] | None = None,
    ) -> list[dict]:
        """List EMR clusters."""
        

    def wait_for_cluster(
        self,
        cluster_id,
        target_state: str = "WAITING",
    ) -> None:
        """Wait until the cluster reaches a target state."""
        waiter_config = {
            "version": 2,
            "waiters": {
                "ClusterWaiting": {
                    "operation": "DescribeCluster",
                    "delay": 30,
                    "maxAttempts": 60,
                    "acceptors": [
                        {
                            "matcher": "path",
                            "argument": "Cluster.Status.State",
                            "expected": target_state,
                            "state": "success",
                        },
                        {
                            "matcher": "path",
                            "argument": "Cluster.Status.State",
                            "expected": "TERMINATED",
                            "state": "failure",
                        },
                        {
                            "matcher": "path",
                            "argument": "Cluster.Status.State",
                            "expected": "TERMINATED_WITH_ERRORS",
                            "state": "failure",
                        },
                    ],
                }
            },
        }

        model = WaiterModel(waiter_config)

        cluster_waiter = create_waiter_with_client(
            "ClusterWaiting",
            model,
            self.emr,
        )

        cluster_waiter.wait(
            ClusterId=cluster_id,
        )

        log.info("cluster %s is %s", self.cluster_id, target_state)


    def terminate_cluster(self) -> None:
        """Terminate the EMR cluster."""
        try:
            response = self.emr.terminate_job_flows(
                JobFlowIds=[
                    self.cluster_id,
                ]
            )
        except ClientError as e:
            log.error("unexpected error: %s", e)

    # ==========================================
    # Spark Connect Session Lifecycle
    # ==========================================

    def start_spark_session(
        self,
        name: str,
        execution_role_arn: str | None = None,
        engine_configuration: dict | None = None,
    ) -> str:
        """Start an interactive Spark Connect session."""
        try:
            response = self.emr.start_session(
                Name=name,
                execution_role_arn=execution_role_arn,
                engine_configuration=engine_configuration
            )
            session_id = response["Id"]

            self.wait_for_spark_session(session_id, "IDLE")
        except ClientError as e:
            log.error("unexpected error: %s", e)
        else:
            return session_id

    def describe_spark_session(self) -> dict:
        """Retrieve Spark Connect session status."""
        ...

    def wait_for_spark_session(
        self,
        session_id: str,
        target_state: str = "IDLE",
    ) -> None:
        """Wait until the Spark Connect session is ready."""
        waiter_config = {
                    "version": 2,
                    "waiters": {
                        "SparkSessionWaiting": {
                            "operation": "GetSession",
                            "delay": 30,
                            "maxAttempts": 60,
                            "acceptors": [
                                {
                                    "matcher": "path",
                                    "argument": "Session.State",
                                    "expected": target_state,
                                    "state": "success",
                                },
                                {
                                    "matcher": "path",
                                    "argument": "Session.State",
                                    "expected": "TERMINATED",
                                    "state": "failure",
                                },
                                {
                                    "matcher": "path",
                                    "argument": "Session.State",
                                    "expected": "TERMINATED_WITH_ERRORS",
                                    "state": "failure",
                                },
                            ],
                        }
                    },
                }
        
        model = WaiterModel(waiter_config)

        cluster_waiter = create_waiter_with_client(
            "SparkSessionWaiting",
            model,
            self.emr,
        )

        cluster_waiter.wait(
            ClusterId=self.cluster_id,
            SessionId=session_id
        )

        log.info("spark session %s is %s", session_id, target_state)

    def get_spark_endpoint(self, session_id) -> dict:
        """Retrieve endpoint URL and authentication token."""
        try:
            response = self.emr.get_session_endpoint(
                ClusterId=self.cluster_id,
                SessionId=session_id
            )
        except ClientError as e:
            log.error("unexpected error: %s", e)
        else:
            return response

    def terminate_spark_session(self) -> None:
        """Terminate the remote Spark Connect session."""
        try:
            response = self.emr.terminate_session(
                ClusterId='string',
                SessionId='string'
            )
        except ClientError as e:
            log.error("unexpected error: %s", e)

    # ==========================================
    # Local PySpark Connection
    # ==========================================

    def build_spark_connect_url(self) -> str:
        """Build the Spark Connect URL using EMR credentials."""
        ...

    def connect_spark(
        self,
        spark_config: dict | None = None,
    ) -> SparkSession:
        """Establish a local PySpark Spark Connect client."""
        ...

    def disconnect_spark(self) -> None:
        """Close the local Spark Connect client."""
        ...

    def refresh_auth_token(self) -> None:
        """Refresh the session endpoint and authentication token."""
        ...

    # ==========================================
    # Job and Step Management
    # ==========================================

    def add_spark_step(
        self,
        name: str,
        script_uri: str,
        arguments: list[str] | None = None,
    ) -> str:
        """Submit a batch Spark step to the EMR cluster."""
        ...

    def describe_step(
        self,
        step_id: str,
    ) -> dict:
        """Retrieve Spark step execution details."""
        ...

    def list_steps(self) -> list[dict]:
        """List cluster steps."""
        ...

    # ==========================================
    # Monitoring and Cleanup
    # ==========================================

    def get_cluster_metrics(self) -> dict:
        """Retrieve available cluster metrics."""
        ...

    def get_step_logs(
        self,
        step_id: str,
    ) -> dict:
        """Retrieve or locate step logs in S3."""
        ...

    def cleanup(self) -> None:
        """Close local connection and optionally terminate remote session."""
        ...
