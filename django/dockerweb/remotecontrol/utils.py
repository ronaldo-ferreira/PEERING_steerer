import os

def set_mux_server(servername, mux_servers):
    """Set the mux_server environtment variables"""
    os.environ['DOCKER_TLS_VERIFY'] = '1'
    os.environ['DOCKER_HOST'] = mux_servers[servername][0]
    os.environ['DOCKER_CERT_PATH'] = mux_servers[servername][1]
    os.environ['DOCKER_MACHINE_NAME'] = mux_servers[servername][2]

def get_mux_env():
    """Shows specificied environments variables"""
    print (os.getenv('DOCKER_TLS_VERIFY'))
    print (os.getenv('DOCKER_HOST'))
    print (os.getenv('DOCKER_CERT_PATH'))
    print (os.getenv('DOCKER_MACHINE_NAME'))