# IOT Sharing Network

- Assignment completed in T3 2022 for COMP3331: Computer Networks and Applications.
- Task was to create a server and client TCP interaction network, which also had the ability to support P2P UDP file transfer.
- This project had a focus on gaining experience with programming network applications.
- Project Spec can be found in `spec.pdf`.
- A final mark of 92.5/100 (18.5/20) was awarded and was worth 20% of final grade.
  - 1 mark was deducted as the EDG command was implemented on server side instead of client
  - 0.5 marks was deducted as UEG was somewhat useless due to incorrect EDG implementation

## Usage

The server can be run with the following command, replacing required parameters (see p.9-10 of spec for more detail):
```sh
python3 server.py SERVER_PORT NUMBER_OF_CONSECUTIVE_FAILED_ATTEMPTS
```

The client can be run with the following command, again replacing required parameters
```sh
python3 client.py SERVER_IP SERVER_PORT CLIENT_UDP_SERVER_PORT
```
