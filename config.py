### Firelens config: ###

version = "0.0.4" # The server's version number.
log_level = "info" # The logging level to display in the output log (trace, debug, info, warning, error, critical).

rate_limit = "50/minute" # The max number of requests to each individual endpoint in a given time.
host_address = "127.0.0.1" # The address to host the server on.
server_port = 8000 # The port number to host the server on.
live_reload = True # Whether or not the server should reload when file changes are made.