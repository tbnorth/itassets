FROM alpine

COPY itassets/requirements.txt /itassets/

RUN apk update \
 && apk upgrade \
 && apk add git openssh-client graphviz ttf-freefont py3-jinja2 py3-lxml py-pip \
 && pip3 install -r /itassets/requirements.txt

# this doesn't work because we want to `-v /some/path:/root/.ssh at runtime
# handled in monitor.py instead
# RUN mkdir -p /root/.ssh \
#  && echo >> /root/.ssh/config 'Host *' \
#  && echo >> /root/.ssh/config '    StrictHostKeyChecking no' \
#  && echo >> /root/.ssh/config '    UserKnownHostsFile=/dev/null'

COPY run_itassets.py monitor.py ./itassets /itassets/
CMD ["python3", "/itassets/run_itassets.py", "/inputs/*.yaml"]
