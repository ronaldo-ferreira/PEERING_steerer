import os

def set_mux_server(servername, mux_servers):
    '''Set the mux_server environtment variables'''
    os.putenv('DOCKER_TLS_VERIFY', '1')
    os.putenv('DOCKER_HOST', mux_servers[servername][0])
    os.putenv('DOCKER_CERT_PATH', mux_servers[servername][1])
    os.putenv('DOCKER_MACHINE_NAME', mux_servers[servername][2])