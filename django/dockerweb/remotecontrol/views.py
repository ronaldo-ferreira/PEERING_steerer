from django.http import HttpResponseRedirect
from django.shortcuts import render
from dockerweb.remotecontrol.forms import ServerForm
from docker import from_env
from dockerweb.remotecontrol.utils import set_mux_server


#TODO: move this to the Django database
mux_servers = {}
mux_servers['xbrivas0'] = ('tcp://10.87.7.130:2376', '/home/brivaldo/.docker/machine/machines/xbrivas0', 'xbrivas0', 'Campo Grande')
mux_servers['xbrivas1'] = ('tcp://10.87.7.131:2376', '/home/brivaldo/.docker/machine/machines/xbrivas1', 'xbrivas1', 'Minas Gerais')


def homeproject(request):

    context = {}
    form = ServerForm(request.POST)

    if request.method == 'POST':
        if form.is_valid():
            form.full_clean()

            # Received the Mux Server Option
            context['remoteserver'] = mux_servers[form.cleaned_data['remoteserver']][3]   # Remote Server Name, third position

            set_mux_server(form.cleaned_data['remoteserver'], mux_servers)
            client = from_env()
            context['dockerlist'] = client.images.list()

            return render(request, 'connected.html', context)

    else:
        context= {}
        form = ServerForm()
        context['form'] = form
        return render(request, 'index.html', context)
