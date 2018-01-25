from django.http import HttpResponse
from django.template import loader
from ssh import SSH
from time import sleep

def index(request):
    template = loader.get_template('web/index.html')
    context = {}

    ssh = SSH()
    # Code to use Docker interface
    #TODO: need to receive the answer from SSH
    stoppedDocker = True

    # First webpage rendering
    if stoppedDocker:
    	context['statusDocker'] = 'stopped'
    else:
	context['statusDocker'] = 'running'

    if(request.POST.get('runContainer')):
    	context['statusDocker'] = 'running'
    	ssh.exec_cmd("docker start bri")
	sleep(5)
    	context['statusSSH'] = str(ssh.exec_cmd("docker ps"))

    if(request.POST.get('stopContainer')):
    	context['statusDocker'] = 'stopped'
    	ssh.exec_cmd("docker stop bri")
	sleep(5)
    	context['statusSSH'] = str(ssh.exec_cmd("docker ps"))

    return HttpResponse(template.render(context,request))
